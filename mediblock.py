import hashlib
import datetime
import json
import os # Needed for file operations

BLOCKCHAIN_FILE = "my_medical_records.json" # Define filename

# --- Block Class ---
class Block:
    def __init__(self, index, timestamp, data, previous_hash, hash_override=None):
        """
        Initializes a block.
        hash_override: Used during loading from file to keep the original hash.
                       If None, the hash is calculated.
        """
        self.index = index
        # Ensure timestamp is a datetime object
        if isinstance(timestamp, str):
             try:
                 # Attempt to parse ISO format string back to datetime
                 self.timestamp = datetime.datetime.fromisoformat(timestamp)
             except ValueError:
                 # Handle potential errors if the format is wrong during loading
                 print(f"Warning: Could not parse timestamp string '{timestamp}'. Using current time.")
                 self.timestamp = datetime.datetime.now()
        elif isinstance(timestamp, datetime.datetime):
             self.timestamp = timestamp
        else:
             print(f"Warning: Invalid timestamp type ({type(timestamp)}). Using current time.")
             self.timestamp = datetime.datetime.now()

        self.data = data # The medical record dictionary
        self.previous_hash = previous_hash
        # Use the provided hash during loading, otherwise calculate it
        self.hash = hash_override if hash_override is not None else self.calculate_hash()

    def calculate_hash(self):
        """Calculates the SHA-256 hash for the block."""
        block_string = str(self.index) + \
                       self.timestamp.isoformat() + \
                       json.dumps(self.data, sort_keys=True) + \
                       str(self.previous_hash)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self):
        """Converts the Block object to a JSON-serializable dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(), # Convert datetime to ISO string
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash # Store the calculated/loaded hash
        }

    @classmethod
    def from_dict(cls, block_dict):
        """Creates a Block instance from a dictionary (loaded from JSON)."""
        return cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'], # Will be parsed in __init__
            data=block_dict['data'],
            previous_hash=block_dict['previous_hash'],
            hash_override=block_dict['hash'] # Pass the original hash
        )

    def __str__(self):
        """String representation of the block for printing."""
        # Ensure timestamp is displayed correctly even if loading failed slightly
        ts_str = self.timestamp.isoformat() if isinstance(self.timestamp, datetime.datetime) else str(self.timestamp)
        return (f"--- Block {self.index} ---\n"
                f"Timestamp: {ts_str}\n"
                f"Previous Hash: {self.previous_hash}\n"
                f"Hash: {self.hash}\n"
                f"Data: {json.dumps(self.data, indent=2, ensure_ascii=False)}\n"
                f"------------------\n")

# --- Blockchain Class ---
class MedicalBlockchain:
    def __init__(self):
        # Chain initialization will be handled by load_or_create method typically
        self.chain = []
        # Define required fields based on your schema
        self.required_fields = [
            "patient_name", "session_date", "main_topics",
            "action_plan", "overall_assessment", "risk_assessment"
        ]
        # Define all possible fields for validation (optional but good)
        self.all_fields = [
             "patient_name", "session_date", "main_topics",
             "patient_reported_mood", "physician_observations",
             "key_insights_or_progress", "action_plan",
             "risk_assessment", "overall_assessment"
        ]

    def _create_genesis_block(self):
        """Creates the first block in the chain."""
        # Only call this if the chain is empty
        if not self.chain:
             genesis_block = Block(0, datetime.datetime.now(), {"type": "genesis", "info": "First Block"}, "0")
             self.chain.append(genesis_block)


    def get_latest_block(self):
        """Returns the most recent block in the chain."""
        if not self.chain:
            return None # Or raise an error, but returning None is safer if chain might be empty
        return self.chain[-1]

    def _validate_data(self, data):
        """Checks if the input data dictionary contains all required fields."""
        if not isinstance(data, dict):
            print("Error: Input data must be a dictionary.")
            return False

        missing_required = [field for field in self.required_fields if field not in data]
        if missing_required:
            print(f"Error: Missing required fields: {', '.join(missing_required)}")
            return False

        if not isinstance(data.get("main_topics"), list):
             print(f"Error: 'main_topics' must be a list (array). Found: {type(data.get('main_topics'))}")
             return False

        return True

    def add_block(self, medical_data):
        """
        Adds a new block (medical record) to the chain after validation.
        Returns True if successful, False otherwise.
        """
        if not self._validate_data(medical_data):
            print("Failed to add block due to invalid data.")
            return False

        # Ensure genesis block exists if chain is empty
        if not self.chain:
            self._create_genesis_block()

        previous_block = self.get_latest_block()
        if previous_block is None: # Should not happen if _create_genesis_block worked
            print("Error: Cannot add block, chain is unexpectedly empty.")
            return False

        new_index = previous_block.index + 1
        new_timestamp = datetime.datetime.now()
        # Calculate hash normally when adding a new block
        new_block = Block(new_index, new_timestamp, medical_data, previous_block.hash)
        self.chain.append(new_block)
        print(f"Successfully added Block {new_index}.")
        return True

    def view_chain(self):
        """Prints all blocks in the chain."""
        if not self.chain:
            print("The blockchain is empty.")
            return
        print("\n--- Medical Record Blockchain ---")
        for block in self.chain:
            print(block)
        print("--- End of Blockchain ---\n")

    def view_previous_records(self, count=None):
        """
        Prints previous medical records (excluding Genesis block).
        :param count: If specified, shows only the last 'count' records.
                      If None, shows all records.
        """
        print("\n--- Viewing Previous Medical Records ---")
        records = self.chain[1:] # Skip Genesis block (index 0)
        if not records:
            print("No medical records found (only Genesis Block exists).")
            return

        if count is not None and count > 0:
            records_to_show = records[-count:]
            print(f"(Showing last {len(records_to_show)} records)")
        else:
            records_to_show = records
            print(f"(Showing all {len(records_to_show)} records)")

        rtn = []
        for block in records_to_show:
             print(f"--- Record (Block {block.index}) ---")
             # Use the block's __str__ method implicitly or format manually
             # print(block) # Simpler way using __str__
             ts_str = block.timestamp.isoformat() if isinstance(block.timestamp, datetime.datetime) else str(block.timestamp)
             print(f"Timestamp: {ts_str}")
             print(f"Data:\n{json.dumps(block.data, indent=2, ensure_ascii=False)}")
             print(f"Hash: {block.hash}")
             print(f"Previous Hash: {block.previous_hash}")
             print("-" * 20)

             rtn.append(block.data) # Collect data for return

        print("--- End of Records View ---\n")

        return rtn

    def is_chain_valid(self):
        """Validates the integrity of the blockchain."""
        if not self.chain:
            print("Blockchain is empty, cannot validate.")
            return True # Or False, depending on definition

        # Check Genesis block (optional, but good practice)
        genesis_block = self.chain[0]
        if genesis_block.index != 0 or genesis_block.previous_hash != "0":
             print("Genesis block invalid.")
             return False
        # Check genesis block's own hash (only if it wasn't loaded with an override)
        # This check might fail if the genesis block was loaded, which is okay.
        # A better check focuses on the *links* between blocks.

        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # 1. Check if the block's stored hash is correct based on its *current* data
            #    Recalculate hash using the same method as when it was created.
            if current_block.hash != current_block.calculate_hash():
                 # Important: If calculate_hash uses current time, this check will always fail for loaded blocks.
                 # Ensure calculate_hash uses the block's *stored* timestamp. (Fixed in Block class)
                print(f"Data Tampering Detected or Hash Mismatch: Block {current_block.index} hash ({current_block.hash}) is invalid. Recalculated hash: {current_block.calculate_hash()}")
                print(f"Data used for recalc: Index={current_block.index}, TS='{current_block.timestamp.isoformat()}', PrevHash='{current_block.previous_hash}', Data='{json.dumps(current_block.data, sort_keys=True)}'")
                return False

            # 2. Check if the block points correctly to the previous block's hash
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain Broken: Block {current_block.index} previous_hash ({current_block.previous_hash}) does not match Block {previous_block.index} hash ({previous_block.hash}).")
                return False
        print("Blockchain integrity verified.")
        return True

    # --- File Operations ---
    def save_chain(self, filename=BLOCKCHAIN_FILE):
        """Saves the entire blockchain to a JSON file."""
        # try:
        chain_data = [block.to_dict() for block in self.chain]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(chain_data, f, indent=4, ensure_ascii=False)
        print(f"Blockchain successfully saved to {filename}")
        # except IOError as e:
        #     print(f"Error saving blockchain to {filename}: {e}")
        # except Exception as e:
        #     print(f"An unexpected error occurred during saving: {e}")

    @classmethod
    def load_chain(cls, filename=BLOCKCHAIN_FILE):
        """Loads the blockchain from a JSON file. Returns a new MedicalBlockchain instance."""
        new_blockchain = cls() # Create a new instance
        if not os.path.exists(filename):
            print(f"Blockchain file '{filename}' not found. Starting a new chain.")
            new_blockchain._create_genesis_block() # Initialize with Genesis
            return new_blockchain

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)

            if not chain_data: # Handle empty file case
                 print(f"Blockchain file '{filename}' is empty. Starting a new chain.")
                 new_blockchain._create_genesis_block()
                 return new_blockchain

            # Reconstruct the chain from the loaded data
            new_blockchain.chain = [Block.from_dict(block_data) for block_data in chain_data]
            print(f"Blockchain successfully loaded from {filename}. Contains {len(new_blockchain.chain)} blocks.")

            # Optional: Validate the loaded chain immediately
            if not new_blockchain.is_chain_valid():
                 print("Warning: Loaded blockchain failed integrity check!")
                 # Decide policy: halt, use anyway, try to repair? For now, just warn.

            return new_blockchain

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {filename}: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain
        except IOError as e:
            print(f"Error reading blockchain file {filename}: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain
        except Exception as e:
            print(f"An unexpected error occurred during loading: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain


# --- User Functions (Unchanged) ---

def input_medical_record(blockchain_instance, record_data):
    print(f"\nAttempting to add record for: {record_data.get('patient_name', 'N/A')}")
    success = blockchain_instance.add_block(record_data)
    if success:
        print("Record added successfully.")
    else:
        print("Failed to add record.")

def view_all_previous_records(blockchain_instance):
    blockchain_instance.view_previous_records()

def view_last_n_records(blockchain_instance, n):
    if isinstance(n, int) and n > 0:
        return blockchain_instance.view_previous_records(count=n)
    else:
        print("Please provide a positive integer for the number of records to view.")


# --- Updated Example Usage ---
if __name__ == "__main__":

    # 1. Load existing blockchain or create a new one
    print(f"--- Loading Blockchain from {BLOCKCHAIN_FILE} ---")
    my_medical_chain = MedicalBlockchain.load_chain()
    print("-------------------------------------------\n")

    # If loading failed or it's the first time, the chain might only have the genesis block.
    # Let's check the number of actual records (blocks after genesis)
    initial_record_count = len(my_medical_chain.chain) - 1 if len(my_medical_chain.chain) > 0 else 0
    print(f"Loaded chain has {initial_record_count} medical records (excluding Genesis).")

    # Optional: View loaded records
    if initial_record_count > 0:
         print("\n--- Viewing Records Loaded From File ---")
         view_all_previous_records(my_medical_chain)


    # --- Simulate Adding New Records ---
    print("\n--- Adding New Records ---")
    # Example: Only add new records if they haven't been added before (e.g., based on date/patient)
    # For simplicity here, we just add new ones. In a real app, you'd prevent duplicates.

    # record_new_1 = {
    #     'patient_reported_mood': '안정적임', 
    #     'patient_name': '제리', 
    #     'risk_assessment': '없음', 
    #     'session_date': '2024-11-02', 
    #     'key_insights_or_progress': '펑션 콜링을 성공적으로 테스트함.', 
    #     'main_topics': ['간단한 펑션 콜링 테스트', '심리 상담 자동화'], 
    #     'physician_observations': '편안하고 적극적인 태도를 보임.', 
    #     'action_plan': '다음 세션에서 심리 상담 자동화에 대한 추가 논의 진행.', 
    #     'overall_assessment': '전반적으로 양호하며, 펑션 콜링 테스트에 대한 이해도가 높음.'
    # }

    record_new_1 = {'main_topics': ['코딩 작업량 증가로 인한 스트레스', '수면 부족', '신앙적 어려움'], 'patient_name': '제리', 'action_plan': '매일 밤 잠들기 전 10분 기도', 'session_date': '2024-07-31', 'overall_assessment': '제리님은 최근 코딩 작업량 증가로 인해 스트레스와 수면 부족을 겪고 있으며, 신앙적인 어려움도 느끼고 있습니다. 규칙적인 수면 습관과 스트레스 해소 방법을 통해 개선할 필요가 있습니다.', 'risk_assessment': '없음', 'physician_observations': '피로한 모습, 불안한 표정', 'patient_reported_mood': '불안함'}
    input_medical_record(my_medical_chain, record_new_1)

    # record_new_2 = {
    #   "patient_name": "김민준", # Existing patient, follow-up
    #   "session_date": "2024-08-20",
    #   "main_topics": ["수면 위생 실천 결과", "스트레스 관리 기술"],
    #   "patient_reported_mood": "안정적임",
    #   "physician_observations": "이전보다 편안해 보이며, 자신의 경험을 명확하게 설명함.",
    #   "key_insights_or_progress": "수면 시간이 꾸준히 증가하고 있으며, 낮 동안의 피로감이 줄었다고 보고함. 스트레스 상황에서 명상을 활용하기 시작함.",
    #   "action_plan": "주 3회 꾸준히 운동하기 추가, 스트레스 유발 요인 목록화.",
    #   "risk_assessment": "없음",
    #   "overall_assessment": "환자는 제시된 전략들을 잘 따르고 있으며 긍정적인 변화를 보이고 있음. 스트레스 관리에 대한 심층적인 논의가 다음 단계로 적절함."
    # }
    # input_medical_record(my_medical_chain, record_new_2)


    # --- View Records After Adding New Ones ---
    print("\n--- Viewing All Records (Including Newly Added) ---")
    view_all_previous_records(my_medical_chain)

    # --- Save the updated blockchain ---
    print("\n--- Saving Updated Blockchain ---")
    #[FN] 함수 호출 중 오류 발생: module 'mediblock' has no attribute 'my_medical_chain'
    my_medical_chain.save_chain()

    # --- Final Integrity Check ---
    print("\n--- Final Integrity Check Before Exiting ---")
    my_medical_chain.is_chain_valid()

    print("\n--- Script Finished ---")