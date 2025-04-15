## pip install --upgrade google-genai==0.3.0 google-generativeai==0.8.3##
## pip install --upgrade google-generativeai

import asyncio
import json
import json.tool
import os
import websockets
from google import genai
import base64
import io
from pydub import AudioSegment
import google.generativeai as generative
import wave
import numpy as np

import mediblock as mb
import config as cfg #define config.py

import timer
import music_play


# Load API key from environment
os.environ['GOOGLE_API_KEY'] = cfg.GOOGLE_API_KEY
generative.configure(api_key=os.environ['GOOGLE_API_KEY'])
MODEL = cfg.MODEL 
TRANSCRIPTION_MODEL = cfg.TRANSCRIPTION_MODEL

SND_TRANSCRIP = cfg.SND_TRANSCRIP
RCV_TRANSCRIP = cfg.RCV_TRANSCRIP

#이전 메디컬 블럭체인 정보 보기
my_medical_chain = mb.MedicalBlockchain.load_chain()

#blockchain 에 signature 로 데이터 위변조를 막도록 데이터에 대한 해쉬코드가 들어가는 것 고려

client = genai.Client(
  http_options={
    'api_version': 'v1alpha',
  }
)

def is_json(obj):
    try:
        json_object = json.loads(obj)
        # { } 가 포함된 string이 invalid json 인 경우 Exception
        iterator = iter(json_object)
        # { } 가 없는 경우는 string의 경우 Exception
    except Exception as e:
        return False
    return True

def print_json_keys_structured(json_data, indent=0, prefix=""):
    """JSON 데이터의 키를 계층적으로 들여쓰기하여 출력하는 함수

    Args:
        json_data: JSON 데이터 (dict, list, 또는 기본 자료형)
        indent: 현재 들여쓰기 레벨 (기본값: 0)
        prefix: 키 앞에 붙일 접두사 (예: "-", "+", ">" 등, 기본값: "")
    """
    indent_str = "  " * indent  # 들여쓰기 공백 생성

    if isinstance(json_data, dict):
        for key, value in json_data.items():
            print(f"{indent_str}{prefix}{key}:") # 키 출력 (접두사, 들여쓰기 적용)
            print_json_keys_structured(value, indent + 1, prefix) # 값에 대해 재귀 호출, 들여쓰기 레벨 증가
    elif isinstance(json_data, list):
        for i, item in enumerate(json_data):
            print(f"{indent_str}{prefix}[{i}]:") # 리스트 인덱스 출력
            print_json_keys_structured(item, indent + 1, prefix) # 리스트 아이템에 대해 재귀 호출
    else:
        # 기본 자료형 값은 키 정보가 아니므로 출력하지 않음 (필요하다면 출력 가능)
        pass # 또는 print(f"{indent_str}{prefix}(value: {json_data})") 와 같이 값도 출력 가능

def calculate_dbfs(pcm_bytes, bit_depth):
    """PCM 데이터에서 dBFS를 계산합니다.

    Args:
        pcm_data: NumPy 배열 형태의 PCM 데이터
        bit_depth: PCM 데이터의 비트 심도 (예: 16, 24)

    Returns:
        dBFS 값 (float)
    """

    pcm_data = np.frombuffer(pcm_bytes, dtype=np.int16)

    max_amplitude = 2**(bit_depth - 1)  # Signed PCM 기준 최대 진폭
    rms = np.sqrt(np.mean(pcm_data**2))

    # RMS 값이 0인 경우 (무음) - 무한대 데시벨 방지
    if rms == 0:
        return -float('inf')  # 또는 적절한 최소값 (예: -100 dBFS)

    dbfs = 20 * np.log10(rms / max_amplitude)
    return dbfs

async def gemini_session_handler(client_websocket: websockets.WebSocketServerProtocol):
    """Handles the interaction with Gemini API within a websocket session."""
    try:
        config_message = await client_websocket.recv()
        # config_data = json.loads(config_message)
        # config = config_data.get("setup", {})
        # print(config)
        # return

        turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
        turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}
        summarize_mental_care_session = {
            "name": "summarize_mental_care_session",
            "description": "주치의가 상담자의 심리 및 멘탈 케어 상담 내용을 요약하고 기록합니다. (Summarizes and records the content of a psychological and mental care counseling session between a primary care physician and a patient.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "상담을 받은 상담자(환자)의 이름. (Name of the patient who received counseling.)"
                    },
                    "session_date": {
                        "type": "string",
                        "description": "상담이 진행된 날짜 (예: '2024-07-30'). (Date the counseling session took place, e.g., '2024-07-30')"
                    },
                    "main_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "상담에서 주로 다루어진 주제 또는 문제 목록. (List of main topics or issues discussed during the session.)"
                    },
                    "patient_reported_mood": {
                        "type": "string",
                        "description": "상담자가 보고한 자신의 기분이나 감정 상태 (예: '불안함', '우울함', '안정적임'). (Patient's self-reported mood or emotional state, e.g., 'Anxious', 'Depressed', 'Stable'.)"
                    },
                    "physician_observations": {
                        "type": "string",
                        "description": "주치의가 관찰한 상담자의 행동, 태도, 또는 중요한 비언어적 신호. (Physician's observations of the patient's behavior, attitude, or significant non-verbal cues.)"
                    },
                    "key_insights_or_progress": {
                        "type": "string",
                        "description": "상담을 통해 얻은 주요 통찰이나 상담자의 진전 사항. (Key insights gained or progress made by the patient during the session.)"
                    },
                    "action_plan": {
                        "type": "string",
                        "description": "다음 상담까지 상담자 또는 주치의가 수행하기로 합의한 구체적인 행동 계획 또는 과제. (Specific action plan or tasks agreed upon for the patient or physician to undertake before the next session.)"
                    },
                    "risk_assessment": {
                        "type": "string",
                        "description": "자해, 타해 위험 등 주치의가 평가한 잠재적 위험 요소 요약 (없을 경우 '없음'). (Summary of potential risk factors assessed by the physician, such as self-harm or harm to others. State 'None' if no risks identified.)"
                    },
                    "overall_assessment":{
                        "type": "string",
                        "description": "상담 내용에 대한 주치의의 전반적인 평가 및 요약. (Physician's overall assessment and summary of the session.)"
                    }
                },
                "required": [
                    "patient_name",
                    "session_date",
                    "main_topics",
                    "action_plan",
                    "overall_assessment",
                    "risk_assessment"
                ]
            }
        }

        retrieve_recent_mental_care_sessions = {
            "name": "retrieve_recent_mental_care_sessions",
            "description": "가장 최근의 심리 및 멘탈 케어 상담 기록을 1개에서 5개까지 조회합니다. 특정 환자를 지정하거나 전체 최근 기록을 조회할 수 있습니다. (Retrieves the most recent mental care counseling session records, between 1 and 5 sessions. Can specify a patient or retrieve overall recent records.)",
            "parameters": {
                "type": "object",
                "properties": {
                "count": {
                    "type": "integer",
                    "description": "조회할 최근 상담 기록의 개수 (1에서 5 사이의 정수). 지정하지 않으면 기본값으로 1개의 가장 최근 기록을 조회합니다. (Number of recent session records to retrieve, an integer between 1 and 5. Defaults to 1 if not specified.)",
                    "minimum": 1,
                    "maximum": 5
                },
                "patient_name": {
                    "type": "string",
                    "description": "(선택사항) 특정 상담자(환자)의 최근 기록만 조회할 경우 이름 지정. 지정하지 않으면 시스템 전체의 최근 기록을 조회합니다. (Optional: Specify the patient's name to retrieve recent records only for that patient. If omitted, retrieves the most recent records across all patients.)"
                }
                },
                "required": [] # count는 기본값이 있으므로 필수는 아님. patient_name도 선택사항.
            }
        }

        get_remaining_timer_time = timer.get_remaining_time_function_json

        list_music_files = music_play.list_files_function_json
        play_music_file = music_play.play_file_function_json

        async def fn_turn_on_the_lights():
            print("fn_turn_on_the_lights: OK")
            # print("fn_turn_on_the_lights:", args)
            return "test OK"
        
        async def fn_summarize_mental_care_session(msg):
            try:
                #print("msg:", msg)
                mb.input_medical_record(my_medical_chain, msg)

                # save 시 전체 종료? 왜?, (수정이 어려율시 마지막 저장 처리로 변경가능)
                # --- Save the updated blockchain ---
                # print("\n--- Saving Updated Blockchain ---")
                # my_medical_chain.save_chain()

                # --- Final Integrity Check ---
                # print("\n--- Final Integrity Check Before Exiting ---")
                # my_medical_chain.is_chain_valid()

                #print("fn_summarize_mental_care_session: OK")
                return "ok"
            except Exception as e:
                print(f"Error in fn_summarize_mental_care_session: {e}")
                return "error"        

        async def fn_retrieve_recent_mental_care_sessions(args):
            try:
                print("args:", args)

                rtn = mb.view_last_n_records(my_medical_chain, args['count'])
                # print("rtn:", rtn)

                return rtn
            except Exception as e:
                print(f"Error in fn_retrieve_recent_mental_care_sessions: {e}")
                return "error"        

        config = {"generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                        "prebuilt_voice_config": {"voice_name": "Aoede"}
                        }
                    }
                    },
                    "system_instruction": {
                        "parts": [
                            {"text": cfg.INSTRUCTION }
                        ]
                        # "role": "system"  # role 필드 제거 - 선택 사항이므로 제거 후 테스트
                    },
                    "tools":[
                        {"google_search": {}},
                        # {'code_execution': {}},
                        {'function_declarations': [summarize_mental_care_session, retrieve_recent_mental_care_sessions, get_remaining_timer_time, list_music_files, play_music_file, turn_on_the_lights_schema, turn_off_the_lights_schema]}
                    ],
                    #automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)                    
                }
        
        # print(">> config:", config)
         
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            session.isPlaying = False
            print("Connected to Gemini API")

            print(">> 타이머 시작:")
            result_start = timer.start_consultation_timer()
            print(f"결과: {result_start}\n") # status: started 예상            

            async def send_to_gemini():
                """Sends messages from the client websocket to the Gemini API."""
                try:
                    temp = b''
                    async for message in client_websocket:
                        try:
                            data = json.loads(message)
                        #   print_json_keys_structured(data, prefix="+ ")
                            if "realtime_input" in data:
                                for chunk in data["realtime_input"]["media_chunks"]:
                                    if chunk["mime_type"] == "audio/pcm":

                                        if SND_TRANSCRIP:
                                            byted_chunk = base64.b64decode(chunk["data"])
                                            temp += byted_chunk
                                            #print("isPlaying:", session.isPlaying, "dbfs_chunk:", calculate_dbfs(byted_chunk, 16), "temp_size:", len(temp))

                                            #응답 not playing , -70 보다 작으면 침묵, temp 크기 0.5초 이상?
                                        #   if not session.isPlaying and calculate_dbfs(byted_chunk, 16) < -70 and len(temp) > 100000:
                                            if not session.isPlaying and calculate_dbfs(byted_chunk, 16) < -70 and len(temp) > 50000:
                                                # Clear the accumulated audio data
                                                # print("[CK]transcribed_text:", transcribed_text)
                                                #print("[OK]Sended to Gemini:", len(temp))
                                                await session.send({"mime_type": "audio/pcm", "data": temp})

                                                transcribed_text = transcribe_audio(temp)
                                                temp = b''

                                                if transcribed_text not in {"<Not recognizable>", "<Not recognizable>\n"}:
                                                    print(f"transcribed_text:[{transcribed_text}]")
                                                    await client_websocket.send(json.dumps({
                                                        "text": "L:"+transcribed_text
                                                    }))
                                        else:
                                            # print("[OK]Sended to Gemini:", len(chunk["data"]), len(temp))
                                            await session.send({"mime_type": "audio/pcm", "data": chunk["data"]})
                                        
                                    elif chunk["mime_type"] == "image/jpeg":
                                        if "data" in chunk.keys():
                                            await session.send({"mime_type": "image/jpeg", "data": chunk["data"]})


                    #   except asyncio.CancelledError: # CancelledError 먼저 처리
                    #       print("[ER]Asyncio Task Cancelled!") # 취소 상황에 대한 특정 처리 (예: 로그만 남기기)

                        except websockets.exceptions.ConnectionClosedOK:
                            print("[SND] Client connection closed normally (send)")
                            break  # Exit the loop if the connection is closed
                        except websockets.exceptions.ConnectionClosedError:
                            print("[SND] Client connection closed ConnectionClosedError (send)")
                            break  # Exit the loop if the connection is closed
                        except Exception as e:
                            print("[SND] Error sending to Gemini:", e)
                        #   print("is_json:", is_json(message), len(message))
                            
                    print("Client connection closed (send)")
                except Exception as e:
                     print(f"Error sending to Gemini: {e}")
                finally:
                   print("send_to_gemini closed")

            async def receive_from_gemini():
                """Receives responses from the Gemini API and forwards them to the client, looping until turn is complete."""
                try:
                    while True:
                        try:
                            print("receiving from gemini")

                            async for response in session.receive():
                                if response.server_content is None:
                                    #print(f'Unhandled server message! - {response}')
                                    if response.tool_call:
                                        print(f'[FN] response.tool_call : {response.tool_call}')

                                        # --- 여기가 추가되어야 할 부분 ---
                                        try:
                                            # 1. 인자 파싱 (구체적인 구조는 response.tool_call 내용 확인 필요)
                                            # 예시: tool_call 객체 구조가 { function_call: { name: 'func_name', args: {'arg1': val1} } } 라고 가정
                                            call_info = response.tool_call.function_calls[0] # 실제 객체 구조에 맞게 수정
                                            function_name = call_info.name
                                            arguments = call_info.args # dict 형태일 것으로 예상

                                            # 2. 함수 식별 및 호출
                                            function_to_call = None
                                            if function_name == 'summarize_mental_care_session':
                                                function_to_call = fn_summarize_mental_care_session
                                            if function_name == 'retrieve_recent_mental_care_sessions':
                                                function_to_call = fn_retrieve_recent_mental_care_sessions
                                            if function_name == 'get_remaining_timer_time':
                                                function_to_call = timer.get_remaining_timer_time
                                            if function_name == 'list_music_files':
                                                function_to_call = music_play.list_music_files
                                            if function_name == 'play_music_file':
                                                function_to_call = music_play.play_music_file
                                            # ... 다른 함수들도 필요하면 추가 ...

                                            if function_to_call:
                                                # 3. 결과 얻기
                                                # result = await function_to_call(**arguments) # **로 딕셔너리 인자 전달
                                                result = await function_to_call(arguments) # **로 딕셔너리 인자 전달
                                                # print(f"[FN] 함수 실행 결과: {result}")
                                                # print("[FN] call_info:", call_info)

                                                msg = [{
                                                        'id': call_info.id,
                                                        'name': call_info.name,
                                                        'response':{'result': result}
                                                }]
                                                await session.send(msg)
                                                print("[FN] Successfully sent function response to Gemini.", msg)

                                                # 클라이언트 화면에 메시지 전달(옵션)
                                                # print("[FN] client_websocket send: ", arguments)
                                                # await client_websocket.send(json.dumps({"text": f"{str(arguments)}"}))                                                

                                            else:
                                                print(f"[FN] 알 수 없는 함수 호출: {function_name}, {function_to_call}")
                                                # 오류 처리 또는 Gemini에게 함수를 찾을 수 없다고 알림

                                        except Exception as e:
                                            print(f"[FN] 함수 호출 중 오류 발생: {e}")
                                            # 오류 처리 및 Gemini에게 알림 (선택적)
                                        # --- 추가 부분 끝 ---

                                    #continue
                                else:

                                    model_turn = response.server_content.model_turn
                                    if model_turn:
                                        for part in model_turn.parts:
                                            if hasattr(part, 'text') and part.text is not None:
                                                await client_websocket.send(json.dumps({"text": part.text}))
                                            elif hasattr(part, 'inline_data') and part.inline_data is not None:
                                                #임시주석처리 print("audio mime_type:", part.inline_data.mime_type)
                                                base64_audio = base64.b64encode(part.inline_data.data).decode('utf-8')
                                                
                                                session.isPlaying = True
                                                #print("[OK]Sended to Client:", len(base64_audio))
                                                await client_websocket.send(json.dumps({"audio": base64_audio}))
                                                
                                                if RCV_TRANSCRIP:
                                                    # Accumulate the audio data here
                                                    if not hasattr(session, 'audio_data'):
                                                        session.audio_data = b''
                                                    session.audio_data += part.inline_data.data
                                                
                                                #임시주석처리 print("audio received")

                                    if RCV_TRANSCRIP:
                                        if response.server_content.turn_complete:
                                            print('\n<Turn complete>')
                                            session.isPlaying = False
                                            # Transcribe the accumulated audio here
                                            transcribed_text = transcribe_audio(session.audio_data)
                                            if transcribed_text:    
                                                await client_websocket.send(json.dumps({
                                                    "text": "R:"+transcribed_text
                                                }))
                                            # Clear the accumulated audio data
                                            session.audio_data = b''
                        except websockets.exceptions.ConnectionClosedOK:
                            print("[RCV] Client connection closed normally (receive)")
                            break  # Exit the loop if the connection is closed
                        except websockets.exceptions.ConnectionClosedError as e:
                            print(f"[RCV] Client connection closed ConnectionClosedError (receive): \n{e}")
                            break  # Exit the loop if the connection is closed
                        except Exception as e:
                            print(f"[RCV] Error receiving from Gemini: \n{e}")
                            #break 

                except Exception as e:
                    print(f"While Loop : Error receiving from Gemini: \n{e}")
                finally:
                    print("While Loop : Gemini connection closed (receive)")

                    # 최종 블럭저장 로직 추가
                    # --- Save the updated blockchain ---
                    print("\n--- Saving Updated Blockchain ---")
                    my_medical_chain.save_chain()

                    # --- Final Integrity Check ---
                    print("\n--- Final Integrity Check Before Exiting ---")
                    my_medical_chain.is_chain_valid()



            # Start send loop
            send_task = asyncio.create_task(send_to_gemini())
            # Launch receive loop as a background task
            receive_task = asyncio.create_task(receive_from_gemini())
            await asyncio.gather(send_task, receive_task)


    except Exception as e:
        print(f"Error in Gemini session: {e}")
    finally:
        print("Gemini session closed.")

def transcribe_audio(audio_data):
    """Transcribes audio using Gemini 1.5 Flash."""
    try:
        # Make sure we have valid audio data
        if not audio_data:
            return "No audio data received."
            
        # Convert PCM to MP3
        mp3_audio_base64 = convert_pcm_to_mp3(audio_data)
        if not mp3_audio_base64:
            return "Audio conversion failed."
            
        # Create a client specific for transcription (assuming Gemini 1.5 flash)
        transcription_client = generative.GenerativeModel(model_name=TRANSCRIPTION_MODEL)
        
        prompt = """Generate a transcript of the speech. 
        Please do not include any other text in the response. 
        If you cannot hear the speech, please only say '<Not recognizable>'."""
        
        response = transcription_client.generate_content(
            [
                prompt,
                {
                    "mime_type": "audio/mp3", 
                    "data": base64.b64decode(mp3_audio_base64),
                }
            ]
        )
            
        return response.text

    except Exception as e:
        print(f"Transcription error: {e}")
        return "Transcription failed.", None

def convert_pcm_to_mp3(pcm_data):
    """Converts PCM audio to base64 encoded MP3."""
    try:
        # Create a WAV in memory first
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(24000)  # 24kHz
            wav_file.writeframes(pcm_data)
        
        # Reset buffer position
        wav_buffer.seek(0)
        
        # Convert WAV to MP3
        audio_segment = AudioSegment.from_wav(wav_buffer)
        
        # Export as MP3
        mp3_buffer = io.BytesIO()
        audio_segment.export(mp3_buffer, format="mp3", codec="libmp3lame")
        
        # Convert to base64
        mp3_base64 = base64.b64encode(mp3_buffer.getvalue()).decode('utf-8')
        return mp3_base64
        
    except Exception as e:
        print(f"Error converting PCM to MP3: {e}")
        return None

import ssl
async def main() -> None:

    # # SSL 컨텍스트 생성
    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # # # 인증서 및 개인 키 파일 경로 (실제 파일 경로로 변경)
    # cert_path = "localhost.crt"  # 생성한 인증서 파일 경로
    # key_path = "localhost.key"    # 생성한 개인 키 파일 경로

    # ssl_context.load_cert_chain(cert_path, key_path, password="zergswim")

    # async with websockets.serve(gemini_session_handler, "localhost", 9083):
    # async with websockets.serve(gemini_session_handler, "0.0.0.0", 9083, ssl=ssl_context):
    async with websockets.serve(gemini_session_handler, "0.0.0.0", 9083):
        print("Running websocket server 0.0.0.0:9083...")

        await asyncio.Future()  # Keep the server running indefinitely


if __name__ == "__main__":
    asyncio.run(main())