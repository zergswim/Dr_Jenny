import asyncio

import mediblock as mb
# import timer
import music_play
import memoryblock
# import agent_memory
#chromadb 변경검토

#이전 메모리 블럭체인 정보 가져오기
memory_chain = memoryblock.AgentMemoryBlockchain.load_chain()
agent_id = "Dr.Jenny"

#이전 메디컬 블럭체인 정보 보기
my_medical_chain = mb.MedicalBlockchain.load_chain()

#blockchain 에 signature 로 데이터 위변조를 막도록 데이터에 대한 해쉬코드가 들어가는 것 고려

# get_remaining_timer_time = timer.get_remaining_time_function_json

list_music_files = music_play.list_files_function_json
play_music_file = music_play.play_file_function_json

record_agent_memory = memoryblock.record_agent_memory_json
recall_agent_memory = memoryblock.recall_agent_memory_json
# record_agent_memory = agent_memory.record_agent_memory_json
# recall_agent_memory = agent_memory.recall_agent_memory_json

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

function_declarations = [record_agent_memory, recall_agent_memory, summarize_mental_care_session, retrieve_recent_mental_care_sessions, list_music_files, play_music_file]

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
    
async def fn_record_agent_memory(args):
    # function calling 호출용
    print("[DEBUG] init. memory_chain", memory_chain)
    # print("[DEBUG] init. agent_memory")
    # print(type(args), args)
    args = dict(args)
    # print(type(args), args)

    # dict.get()을 사용하여 키가 없을 경우 None을 기본값으로 가져옵니다.
    context_summary = args.get("context_summary")
    current_goal = args.get("current_goal")
    session_id = args.get("session_id")

    memory_chain.record_memory(
    # result = await agent_memory.record_agent_memory(
        agent_id="Dr.Jenny",
        memory_payload=args["memory_payload"], # 키가 없으면 KeyError 발생 (원래 코드와 동일)
        context_summary=context_summary,
        current_goal=current_goal,
        session_id=session_id
    )

    return "ok"

    # if result:
    #     return "saved"
    # else:
    #     return "error"

    # 튕금.. 방지법은?
    #await asyncio.to_thread(memory_chain.save_chain())

async def fn_recall_agent_memory(args):
    # print(args)
    # result = await agent_memory.recall_agent_memory(agent_id="Dr.Jenny")
    # if result:
    #     return result
    # else:
    #     return "error"
    return memory_chain.recall_latest_memory(agent_id, num_to_recall=5)

available_functions = {
    "summarize_mental_care_session": fn_summarize_mental_care_session,
    "retrieve_recent_mental_care_sessions": fn_retrieve_recent_mental_care_sessions,
    # "get_remaining_timer_time": timer.get_remaining_timer_time,
    "list_music_files": music_play.list_music_files,
    "play_music_file": music_play.play_music_file,
    "record_agent_memory": fn_record_agent_memory,
    "recall_agent_memory": fn_recall_agent_memory,
}

async def main():
    print(available_functions)

if __name__ == "__main__":
    # Ensure you have aiofiles installed: pip install aiofiles
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nAn error occurred during execution: {e}")