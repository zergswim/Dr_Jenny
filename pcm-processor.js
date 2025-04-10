/**
 * RingBuffer class (이전과 동일)
 */
class RingBuffer {
    // ... (이전 RingBuffer 코드와 동일) ...
    constructor(size) {
        if (size <= 0 || !Number.isInteger(size)) {
            throw new Error("RingBuffer size must be a positive integer.");
        }
        this._buffer = new Float32Array(size);
        this._size = size;
        this._writeIndex = 0;
        this._readIndex = 0;
        this._availableSamples = 0;
    }

    get capacity() {
        return this._size;
    }

    get availableRead() {
        return this._availableSamples;
    }

    get availableWrite() {
        return this._size - this._availableSamples;
    }

    write(data) {
        const dataLen = data.length;
        if (dataLen === 0) return true;
        // Note: Overflow check is now primarily done *before* calling write in PCMProcessor
        if (dataLen > this.availableWrite) {
             // This should ideally not be reached if pre-check is done
             console.error(`[RingBuffer-Write] Internal Error: Write called despite insufficient space. Tried ${dataLen}, available ${this.availableWrite}`);
             return false;
        }

        const remainingToEnd = this._size - this._writeIndex;
        if (dataLen <= remainingToEnd) {
            this._buffer.set(data, this._writeIndex);
            this._writeIndex += dataLen;
            if (this._writeIndex === this._size) this._writeIndex = 0;
        } else {
            const firstChunkSize = remainingToEnd;
            const secondChunkSize = dataLen - firstChunkSize;
            this._buffer.set(data.subarray(0, firstChunkSize), this._writeIndex);
            this._buffer.set(data.subarray(firstChunkSize), 0);
            this._writeIndex = secondChunkSize;
        }
        this._availableSamples += dataLen;
        return true;
    }

    read(targetArray, samplesToRead = targetArray.length) {
        if (samplesToRead === 0) return 0;
        const actualSamplesToRead = Math.min(samplesToRead, this.availableRead);
        if (actualSamplesToRead === 0) return 0;

        const remainingToEnd = this._size - this._readIndex;
        if (actualSamplesToRead <= remainingToEnd) {
            targetArray.set(this._buffer.subarray(this._readIndex, this._readIndex + actualSamplesToRead), 0);
            this._readIndex += actualSamplesToRead;
            if (this._readIndex === this._size) this._readIndex = 0;
        } else {
            const firstChunkSize = remainingToEnd;
            const secondChunkSize = actualSamplesToRead - firstChunkSize;
            targetArray.set(this._buffer.subarray(this._readIndex, this._readIndex + firstChunkSize), 0);
            targetArray.set(this._buffer.subarray(0, secondChunkSize), firstChunkSize);
            this._readIndex = secondChunkSize;
        }
        this._availableSamples -= actualSamplesToRead;
        return actualSamplesToRead;
    }

    clear() {
        this._readIndex = 0;
        this._writeIndex = 0;
        this._availableSamples = 0;
    }
}


// --- PCMProcessor with explicit buffer size logging ---

class PCMProcessor extends AudioWorkletProcessor {
    static RENDER_QUANTUM_FRAMES = 128;
    // 기본 버퍼 시간을 더 늘려볼 수 있습니다 (예: 10초). 하지만 근본 원인 해결이 더 중요합니다.
    static RECOMMENDED_BUFFER_DURATION_SECONDS = 180.0; // <--- 필요시 더 늘려보세요 (e.g., 10.0)

    constructor(options) {
        super();

        // --- Calculate Buffer Size ---
        const currentSampleRate = sampleRate; // provided by AudioWorkletGlobalScope
        let effectiveSampleRate = currentSampleRate;
        if (!effectiveSampleRate || effectiveSampleRate <= 0) {
             console.error("[PCMProcessor] sampleRate not available or invalid in constructor. Falling back to 48000 Hz for buffer calculation.");
             effectiveSampleRate = 48000;
        }

        let requestedBufferSize = options?.processorOptions?.bufferSize;
        let calculatedDefaultBufferSize = Math.round(effectiveSampleRate * PCMProcessor.RECOMMENDED_BUFFER_DURATION_SECONDS);

        let finalBufferSize;
        if (requestedBufferSize && requestedBufferSize > 0) {
            finalBufferSize = requestedBufferSize;
             console.log(`[PCMProcessor] Using requested buffer size via processorOptions: ${finalBufferSize} samples.`);
        } else {
            finalBufferSize = calculatedDefaultBufferSize;
             console.log(`[PCMProcessor] Using calculated default buffer size: ${finalBufferSize} samples (${PCMProcessor.RECOMMENDED_BUFFER_DURATION_SECONDS}s at ${effectiveSampleRate} Hz).`);
        }

        // 최소 크기 보장 강화 (렌더링 블록의 8배 정도로 여유롭게)
        const minBufferSize = PCMProcessor.RENDER_QUANTUM_FRAMES * 8;
        if (finalBufferSize < minBufferSize) {
             console.warn(`[PCMProcessor] Determined buffer size ${finalBufferSize} is smaller than minimum ${minBufferSize}. Adjusting to minimum.`);
             finalBufferSize = minBufferSize;
        }

        // --- Initialize RingBuffer & Log Actual Capacity ---
        try {
            this._ringBuffer = new RingBuffer(finalBufferSize);
            // !!!! 중요: 실제 생성된 버퍼 크기 확인 !!!!
            console.log(`[PCMProcessor] RingBuffer successfully initialized. Actual capacity: ${this._ringBuffer.capacity} samples.`);
        } catch (error) {
            console.error("[PCMProcessor] Failed to initialize RingBuffer:", error);
            // 실패 시 처리 (예: 프로세서 비활성화)
            this._ringBuffer = null; // Mark as unusable
             return; // Stop constructor
        }


        // --- State Variables ---
        this._isBufferEmptyLogged = false;
        this._isBufferFullLogged = false;

        // --- Message Handling ---
        this.port.onmessage = (e) => {
            // 프로세서 초기화 실패 시 메시지 무시
            if (!this._ringBuffer) return;

            const newData = e.data;
            if (!(newData instanceof Float32Array) || newData.length === 0) {
                return; // Ignore invalid data silently
            }

            // !!!! 중요: 메인 스레드에서 보내는 데이터 크기 확인 !!!!
            // console.log(`[PCMProcessor] Received data chunk size: ${newData.length}`); // 디버깅 시 이 로그 활성화

            const availableWriteSpace = this._ringBuffer.availableWrite;
            if (newData.length > availableWriteSpace) {
                if (!this._isBufferFullLogged) {
                    console.warn(`[PCMProcessor] RingBuffer overflow! Trying to write ${newData.length} samples, but only ${availableWriteSpace} space available. Buffer capacity: ${this._ringBuffer.capacity}. Data dropped. Consider reducing chunk size from main thread or increasing buffer capacity.`);
                    this._isBufferFullLogged = true;
                }
                // 데이터 버림 - 쓰기 시도 안 함
                return;
            }

            // 정상 쓰기
            if (this._ringBuffer.write(newData)) {
                // 쓰기 성공 시 플래그 리셋 (언더플로우, 오버플로우 둘 다)
                this._isBufferEmptyLogged = false;
                this._isBufferFullLogged = false;
            }
            // RingBuffer.write 실패 케이스는 로직상 발생하면 안 됨 (위에서 사전 차단)
        };
    }

    process(inputs, outputs, parameters) {
        // 프로세서 초기화 실패 시 아무 작업 안 함
        if (!this._ringBuffer) return false; // Return false to potentially stop the processor

        const output = outputs[0];
        const channelData = output[0];
        const requestedSamples = channelData.length;

        const samplesRead = this._ringBuffer.read(channelData, requestedSamples);

        if (samplesRead < requestedSamples) {
            if (!this._isBufferEmptyLogged) {
                // console.warn(`[PCMProcessor] Buffer underflow: Needed ${requestedSamples}, got ${samplesRead}. Filling silence.`); // 로그 너무 많으면 주석 처리
                this._isBufferEmptyLogged = true;
            }
            channelData.fill(0, samplesRead, requestedSamples);
        } else {
            this._isBufferEmptyLogged = false;
        }

        // 오버플로우 상태에서 버퍼 공간이 다시 확보되면 로그 플래그 리셋
        if (this._isBufferFullLogged && this._ringBuffer.availableWrite > this._ringBuffer.capacity / 2) {
             // console.log("[PCMProcessor] Buffer space recovered."); // 필요 시 로그
            this._isBufferFullLogged = false;
        }

        return true; // Keep processor alive
    }
}

registerProcessor('pcm-processor', PCMProcessor);


// class PCMProcessor extends AudioWorkletProcessor {
//     constructor() {
//         super();
//         this.buffer = new Float32Array();

//         // Correct way to handle messages in AudioWorklet
//         this.port.onmessage = (e) => {
//             const newData = e.data;
//             const newBuffer = new Float32Array(this.buffer.length + newData.length);
//             newBuffer.set(this.buffer);
//             newBuffer.set(newData, this.buffer.length);
//             this.buffer = newBuffer;
//         };
//     }

//     process(inputs, outputs, parameters) {
//         const output = outputs[0];
//         const channelData = output[0];

//         if (this.buffer.length >= channelData.length) {
//             channelData.set(this.buffer.slice(0, channelData.length));
//             this.buffer = this.buffer.slice(channelData.length);
//             return true;
//         }

//         return true;
//     }
// }

// registerProcessor('pcm-processor', PCMProcessor);