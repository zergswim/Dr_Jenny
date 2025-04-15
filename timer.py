import datetime
import json
import time # 예제 실행 시 시간 지연을 위해 추가
import asyncio

# --- 전역 상태 변수 ---
# 주의: 이 변수들은 스크립트 실행 동안만 유지됩니다.
#      웹 서버 환경 등에서는 요청 간 상태 유지가 보장되지 않습니다.
timer_end_time = None
timer_active = False
timer_duration_minutes = 10 # 타이머 지속 시간 (분)

# --- 타이머 관리 함수 ---

def start_consultation_timer() -> dict:
  """
  전역 10분 상담 타이머를 시작합니다.
  이미 타이머가 활성 상태이면, 새로 시작하지 않고 현재 상태를 알립니다.

  Returns:
      dict: 타이머 시작 결과 또는 현재 상태.
            {'status': 'started'|'already_active', 'message': str, 'end_time_iso': str|None}
            - status: 'started' (새로 시작됨), 'already_active' (이미 실행 중)
            - message: 상태 설명 메시지
            - end_time_iso: 타이머 종료 예정 시간 (ISO 형식, 새로 시작된 경우)
  """
  global timer_end_time, timer_active, timer_duration_minutes

  # if timer_active:
  #   # 이미 타이머가 활성화된 경우
  #   end_time_str = timer_end_time.isoformat(timespec='seconds') if timer_end_time else "알 수 없음"
  #   return {
  #       "status": "already_active",
  #       "message": f"타이머가 이미 실행 중입니다. 종료 예정 시간: {end_time_str}",
  #       "end_time_iso": end_time_str
  #   }
  # else:
  # 새 타이머 시작
  now = datetime.datetime.now()
  duration = datetime.timedelta(minutes=timer_duration_minutes)
  timer_end_time = now + duration
  timer_active = True
  end_time_str = timer_end_time.isoformat(timespec='seconds')
  print(f"타이머 시작됨. 종료 예정: {end_time_str}") # 로그 출력 (선택 사항)
  return {
      "status": "started",
      "message": f"{timer_duration_minutes}분 타이머가 시작되었습니다.",
      "end_time_iso": end_time_str
  }

async def get_remaining_timer_time(args) -> dict:
  """
  현재 활성화된 전역 상담 타이머의 남은 시간을 확인합니다.

  Returns:
      dict: 타이머 상태 및 남은 시간 정보.
            {'status': 'running'|'expired'|'inactive'|'error',
             'remaining_minutes': int,
             'remaining_seconds': int,
             'message': str}
            - status: 'running' (실행 중), 'expired' (시간 만료), 'inactive' (시작되지 않음), 'error' (내부 오류)
            - remaining_minutes: 남은 분 (만료/비활성/오류 시 0)
            - remaining_seconds: 남은 초 (만료/비활성/오류 시 0)
            - message: 상태 설명 메시지
  """
  global timer_end_time, timer_active

  if not timer_active:
    return {
        "status": "inactive",
        "remaining_minutes": 0,
        "remaining_seconds": 0,
        "message": "상담 타이머가 시작되지 않았습니다."
    }

  if timer_end_time is None:
     # 이론적으로 timer_active가 True면 timer_end_time은 None이 아니어야 함 (방어 코드)
     return {
        "status": "error",
        "remaining_minutes": 0,
        "remaining_seconds": 0,
        "message": "타이머 상태 오류 발생."
    }

  now = datetime.datetime.now()
  remaining_delta = timer_end_time - now
  total_seconds_remaining = remaining_delta.total_seconds()

  if total_seconds_remaining <= 0:
    # 시간 만료 (만료 후에도 timer_active는 유지될 수 있음, 필요시 리셋 로직 추가)
    # timer_active = False # 필요하다면 여기서 비활성화
    return {
        "status": "expired",
        "remaining_minutes": 0,
        "remaining_seconds": 0,
        "message": f"설정된 {timer_duration_minutes}분이 경과했습니다."
    }
  else:
    # 아직 시간 남음
    minutes = int(total_seconds_remaining // 60)
    seconds = int(total_seconds_remaining % 60)
    return {
        "status": "running",
        "remaining_minutes": minutes,
        "remaining_seconds": seconds,
        "message": f"남은 시간: {minutes:02d}분 {seconds:02d}초"
    }

# --- Function Calling JSON 정의 ---

# 1. 타이머 시작 함수 정의
start_timer_function_json = {
    "name": "start_consultation_timer",
    "description": f"새로운 {timer_duration_minutes}분 상담 타이머를 시작합니다. 이미 타이머가 실행 중이면 새로 시작하지 않고 현재 상태를 알립니다.",
    "parameters": {
      "type": "object",
      "properties": {} # 입력 파라미터 없음
    }
}

# 2. 남은 시간 확인 함수 정의
get_remaining_time_function_json = {
    "name": "get_remaining_timer_time",
    "description": f"현재 실행 중인 {timer_duration_minutes}분 상담 타이머의 남은 시간을 확인합니다. 타이머가 시작되지 않았거나 시간이 만료된 경우 해당 상태를 반환합니다.",
    "parameters": {
        "type": "object",
        "properties": {} # 입력 파라미터 없음
    }
}

# --- 스크립트 실행 시 예제 코드 ---
if __name__ == "__main__":
    print("--- Function Calling JSON 정의 ---")
    print("1. 타이머 시작 함수:")
    print(json.dumps(start_timer_function_json, indent=2, ensure_ascii=False))
    print("\n2. 남은 시간 확인 함수:")
    print(json.dumps(get_remaining_time_function_json, indent=2, ensure_ascii=False))
    print("\n" + "="*40 + "\n")

    print("--- 함수 사용 시뮬레이션 ---")

    # 1. 타이머 시작 전 남은 시간 확인 시도
    print(">> 남은 시간 확인 (시작 전):")
    result_before_start = get_remaining_timer_time({})
    print(f"결과: {result_before_start}\n") # status: inactive 예상

    # 2. 타이머 시작
    print(">> 타이머 시작:")
    result_start = start_consultation_timer()
    print(f"결과: {result_start}\n") # status: started 예상

    # 3. 타이머 시작 직후 남은 시간 확인
    print(">> 남은 시간 확인 (시작 직후):")
    result_after_start = get_remaining_timer_time({})
    print(f"결과: {result_after_start}\n") # status: running, 약 10분 남음 예상

    # 4. 이미 시작된 상태에서 다시 시작 시도
    print(">> 타이머 다시 시작 시도:")
    result_start_again = start_consultation_timer()
    print(f"결과: {result_start_again}\n") # status: already_active 예상

    # 5. 시간 경과 시뮬레이션 (예: 9분 58초 경과)
    # 실제 사용 시에는 이 부분이 필요 없으며, 시간이 자연스럽게 흐릅니다.
    # 예제를 위해 타이머 종료 시간을 과거로 조작
    print(f">> {timer_duration_minutes - 0.03:.2f}분 경과 시뮬레이션...")
    if timer_active and timer_end_time:
      timer_end_time = datetime.datetime.now() + datetime.timedelta(seconds=2) # 2초 남도록 조작

    # 6. 종료 임박 시 남은 시간 확인
    time.sleep(0.5) # 약간의 시간 지연
    print(">> 남은 시간 확인 (종료 임박):")
    result_near_end = get_remaining_timer_time({})
    print(f"결과: {result_near_end}\n") # status: running, 0분 1초 정도 남음 예상

    # 7. 시간 만료 시뮬레이션
    print(">> 시간 만료 대기 (약 2초)...")
    time.sleep(2)

    # 8. 만료 후 남은 시간 확인
    print(">> 남은 시간 확인 (만료 후):")
    result_expired = get_remaining_timer_time({})
    print(f"결과: {result_expired}\n") # status: expired 예상