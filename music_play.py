import asyncio
import os
import json
import platform
import subprocess # Added for more control over player execution if needed
import logging # Added for better logging

# --- Configuration ---
MP3_BASE_DIR = "D:\\SD\\MP3" # Target directory (Use double backslashes or raw strings)
MUSIC_EXTENTIONS = [".mp3", ".m4a", ".wma"] # Supported music file extensions

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Function for Running Blocking Code Async ---
async def run_blocking(func, *args):
  """Runs a blocking function in a separate thread."""
  # Prefer asyncio.to_thread if available (Python 3.9+)
  if hasattr(asyncio, 'to_thread'):
    return await asyncio.to_thread(func, *args)
  else:
    # Fallback for older Python versions
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

# --- Function 1: List MP3 Files ---

async def list_music_files(args) -> dict:
  """
  Recursively lists all Music files within a specified directory and its subdirectories.

  Args:
      directory_path (str, optional): The base directory to search.
                                      Defaults to MP3_BASE_DIR ("D:\\SD\\MP3").

  Returns:
      dict: A dictionary containing the search results.
            {'status': 'success'|'error'|'not_found',
             'directory': str,
             'file_count': int,
             'files': list[str]|None,
             'message': str}
            - status: 'success' (found files), 'error' (OS error), 'not_found' (directory missing or no files found)
            - directory: The directory that was searched.
            - file_count: Number of Music files found.
            - files: A list of full paths to the Music files, or None on error/not found.
            - message: A descriptive message about the outcome.
  """
  directory_path = MP3_BASE_DIR
  logging.info(f"Attempting to list Music files in: {directory_path}")

  def find_files():
    """Blocking function to find Music files."""
    if not os.path.isdir(directory_path):
      logging.warning(f"Directory not found: {directory_path}")
      return None # Indicate directory not found

    mp3_files = []
    try:
      for root, _, files in os.walk(directory_path):
        for filename in files:
          # if filename.lower().endswith(".mp3") or filename.lower().endswith(".m4a"):
          for ext in MUSIC_EXTENTIONS:
            if filename.lower().endswith(ext):
              full_path = os.path.join(root, filename).replace(MP3_BASE_DIR, "")
              mp3_files.append(full_path)
      return mp3_files
    except OSError as e:
      logging.error(f"OS Error while searching directory {directory_path}: {e}")
      raise # Re-raise to be caught by the outer handler

  try:
    found_files = await run_blocking(find_files)

    if found_files is None: # Directory didn't exist
      return {
          "status": "not_found",
          "directory": directory_path,
          "file_count": 0,
          "files": None,
          "message": f"Error: Directory '{directory_path}' does not exist or is not accessible."
      }
    elif not found_files: # Directory exists but no MP3s
       return {
          "status": "not_found",
          "directory": directory_path,
          "file_count": 0,
          "files": [],
          "message": f"No Music files found in '{directory_path}' or its subdirectories."
      }
    else: # Files found
      logging.info(f"Found {len(found_files)} Music files in {directory_path}.")
      return {
          "status": "success",
          "directory": directory_path,
          "file_count": len(found_files),
          "files": found_files,
          "message": f"Successfully listed {len(found_files)} Music files."
      }
  except OSError as e: # Catch errors raised from find_files
    return {
        "status": "error",
        "directory": directory_path,
        "file_count": 0,
        "files": None,
        "message": f"An OS error occurred while accessing '{directory_path}': {e}"
    }
  except Exception as e: # Catch any other unexpected errors
    logging.exception(f"Unexpected error in list_mp3_files for {directory_path}: {e}")
    return {
        "status": "error",
        "directory": directory_path,
        "file_count": 0,
        "files": None,
        "message": f"An unexpected error occurred: {e}"
    }

# --- Function 2: Play MP3 File ---

async def play_music_file(args) -> dict:
  """
  Plays the specified Music file using the default system player on Windows.

  Args:
      file_path (str): The full path to the Music file to be played.

  Returns:
      dict: A dictionary indicating the outcome.
            {'status': 'success'|'error'|'not_found'|'unsupported_os',
             'file_path': str,
             'message': str}
            - status: 'success' (play command issued), 'error' (failed to play),
                      'not_found' (file doesn't exist), 'unsupported_os' (not Windows)
            - file_path: The path of the file attempted to play.
            - message: A descriptive message.
  """
  file_path = MP3_BASE_DIR + args.get("file_path", None)
  logging.info(f"Attempting to play MP3 file: {file_path}")

  if platform.system() != "Windows":
    logging.warning("Attempted to play file on a non-Windows OS.")
    return {
        "status": "unsupported_os",
        "file_path": file_path,
        "message": "Error: This function only works on Windows."
    }

  def start_file():
    """Blocking function to start the file."""
    if not os.path.exists(file_path):
      logging.warning(f"File not found: {file_path}")
      return False # Indicate file not found

    # if not file_path.lower().endswith(".mp3"):
    #    logging.warning(f"File is not an MP3: {file_path}")
       # Decide if you want to proceed or return an error
       # For now, let's proceed but log a warning. Could return an error status too.

    try:
      # os.startfile is the simplest way on Windows to open a file
      # with its default application. It's non-blocking itself
      # but we run it via run_blocking for consistency and potential
      # slight delays in OS interaction.
      os.startfile(file_path)
      logging.info(f"Issued command to play: {file_path}")
      return True # Command issued successfully
    except OSError as e:
      logging.error(f"OS Error trying to start file {file_path}: {e}")
      raise # Re-raise to be caught by the outer handler
    except Exception as e: # Catch other potential errors like file association issues
       logging.error(f"Failed to start file {file_path}: {e}")
       raise # Re-raise

  try:
    success = await run_blocking(start_file)

    if success:
      return {
          "status": "success",
          "file_path": file_path,
          "message": f"Attempting to play '{os.path.basename(file_path)}' using the default player."
      }
    else: # File not found case handled within start_file
       return {
          "status": "not_found",
          "file_path": file_path,
          "message": f"Error: File not found at path: '{file_path}'"
      }
  except Exception as e: # Catch errors raised from start_file
    return {
        "status": "error",
        "file_path": file_path,
        "message": f"Failed to play file '{file_path}'. Error: {e}"
    }

# --- Function Calling JSON Definitions ---

list_files_function_json = {
    "name": "list_music_files",
    "description": f"음악 파일 목록을 검색하여 반환합니다.",
    "parameters": {
      "type": "object",
      "properties": {}
    }
}

play_file_function_json = {
    "name": "play_music_file",
    "description": "제공된 경로를 사용하여 윈도우의 기본 미디어 플레이어로 특정 music 파일을 재생합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
            "type": "string",
            "description": "재생할 music 파일의 윈도우 경로 (예: '\\Artist\\Song Title.mp3'). list_music_files 함수에서 얻은 경로를 사용해야 합니다."
            }
        },
        "required": ["file_path"]
    }
}

# --- Example Usage ---
async def main():

  # list_result = await list_music_files({}) # Use default path
  # print(f"결과: \n")
  # for idx, l in enumerate(list_result['files']):
  #   print(idx, l)

  play_result = await play_music_file({'file_path': '\\City of angel OST.mp3'})
  print(f"결과: {json.dumps(play_result, indent=2, ensure_ascii=False)}\n")

  # print("--- Function Calling JSON 정의 ---")
  # print("1. MP3 파일 목록 함수:")
  # print(json.dumps(list_files_function_json, indent=2, ensure_ascii=False))
  # print("\n2. MP3 파일 재생 함수:")
  # print(json.dumps(play_file_function_json, indent=2, ensure_ascii=False))
  # print("\n" + "="*40 + "\n")

  # print(f"--- 함수 사용 시뮬레이션 (대상 폴더: {MP3_BASE_DIR}) ---")
  # Note: For this test to work meaningfully, the directory D:\SD\MP3
  # should exist and contain some MP3 files on your Windows system.
  # If it doesn't exist, you'll see the 'not_found' status.

  # # 1. List MP3 files
  # print(">> MP3 파일 목록 가져오기:")
  # list_result = await list_mp3_files({}) # Use default path
  # print(f"결과: {json.dumps(list_result, indent=2, ensure_ascii=False)}\n")

  # # 2. Simulate LLM choosing a file and play it
  # if list_result["status"] == "success" and list_result["files"]:
  #   file_to_play = list_result["files"][0] # Play the first file found
  #   print(f">> '{os.path.basename(file_to_play)}' 파일 재생 시도:")
  #   play_result = await play_mp3_file(file_path=file_to_play)
  #   print(f"결과: {json.dumps(play_result, indent=2, ensure_ascii=False)}\n")
  # elif list_result["status"] == "not_found":
  #    print(">> 재생할 파일 없음 (폴더/파일 없음).\n")
  # else:
  #    print(f">> 파일 목록 가져오기 실패 ({list_result['status']}), 재생 건너뜀.\n")

  # # 3. Test playing a non-existent file
  # print(">> 존재하지 않는 파일 재생 시도:")
  # non_existent_path = os.path.join(MP3_BASE_DIR, "non_existent_song.mp3")
  # play_result_non_existent = await play_mp3_file(file_path=non_existent_path)
  # print(f"결과: {json.dumps(play_result_non_existent, indent=2, ensure_ascii=False)}\n") # Expect 'not_found'

  # 4. Test listing from a non-existent directory (Example)
  # print(">> 존재하지 않는 디렉토리에서 목록 가져오기 시도:")
  # list_result_bad_dir = await list_mp3_files(directory_path="D:\\NonExistentDir\\")
  # print(f"결과: {json.dumps(list_result_bad_dir, indent=2, ensure_ascii=False)}\n") # Expect 'not_found'

if __name__ == "__main__":
  # Ensure running on Windows for the play function test
  # if platform.system() != "Windows":
  #   print("Warning: File playback simulation requires Windows.")
  #   # Decide if you want to exit or just show the JSON definitions
  #   # exit()

  asyncio.run(main())