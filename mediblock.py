import hashlib
import datetime
import json
import os # Needed for file operations

BLOCKCHAIN_FILE = "my_medical_records_signed.json" # Define filename (updated)

# --- Signature Helper Function ---
def calculate_data_signature(data):
    """
    Calculates the SHA-256 hash (checksum) of the given data for integrity verification.
    Handles various data types by converting to a sorted JSON string.
    """
    # Use json.dumps for consistent string representation of data (dicts, lists, etc.)
    # sort_keys=True ensures dictionaries produce the same string regardless of key insertion order.
    data_string = json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(data_string).hexdigest()

# --- Block Class ---
class Block:
    def __init__(self, index, timestamp, data, signature, previous_hash, hash_override=None): # Added signature
        """
        Initializes a block.
        signature: SHA-256 hash of the 'data' field for integrity check.
        hash_override: Used during loading from file to keep the original hash.
                       If None, the hash is calculated.
        """
        self.index = index
        # Ensure timestamp is a datetime object
        if isinstance(timestamp, str):
            try:
                self.timestamp = datetime.datetime.fromisoformat(timestamp)
            except ValueError:
                print(f"Warning: Could not parse timestamp string '{timestamp}'. Using current time.")
                self.timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0) # Use UTC and remove microseconds
        elif isinstance(timestamp, datetime.datetime):
            # Ensure timezone awareness (use UTC if naive) and remove microseconds for consistency
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
            self.timestamp = timestamp.replace(microsecond=0)
        else:
            print(f"Warning: Invalid timestamp type ({type(timestamp)}). Using current UTC time.")
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

        self.data = data # The medical record dictionary
        self.signature = signature # Store the data's signature (checksum hash)
        self.previous_hash = previous_hash
        # Use the provided hash during loading, otherwise calculate it
        self.hash = hash_override if hash_override is not None else self.calculate_hash()

    def calculate_hash(self):
        """
        Calculates the SHA-256 hash for the entire block, including the data signature.
        """
        block_string = str(self.index) + \
                       self.timestamp.isoformat() + \
                       json.dumps(self.data, sort_keys=True, ensure_ascii=False) + \
                       str(self.signature) + \
                       str(self.previous_hash) # Include signature in the block hash
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

    def is_data_valid(self):
        """
        Verifies if the stored data matches its signature.
        Returns True if the data has not been tampered with, False otherwise.
        """
        return self.signature == calculate_data_signature(self.data)

    def to_dict(self):
        """Converts the Block object to a JSON-serializable dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(), # Convert datetime to ISO string
            "data": self.data,
            "signature": self.signature, # Add signature to dictionary
            "previous_hash": self.previous_hash,
            "hash": self.hash # Store the calculated/loaded hash
        }

    @classmethod
    def from_dict(cls, block_dict):
        """Creates a Block instance from a dictionary (loaded from JSON)."""
        # Check if 'signature' key exists for backward compatibility (optional)
        signature = block_dict.get('signature', None)
        if signature is None:
             # Handle older blocks without signature: calculate it now or log a warning
             print(f"Warning: Block {block_dict.get('index', 'N/A')} loaded without a signature. Calculating now.")
             signature = calculate_data_signature(block_dict['data'])
             # Note: This assumes the loaded data *is* the original data.
             # If data could have been tampered *before* loading, this won't catch it.

        return cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'], # Will be parsed in __init__
            data=block_dict['data'],
            signature=signature, # Pass the loaded or calculated signature
            previous_hash=block_dict['previous_hash'],
            hash_override=block_dict['hash'] # Pass the original block hash
        )

    def __str__(self):
        """String representation of the block for printing."""
        ts_str = self.timestamp.isoformat() if isinstance(self.timestamp, datetime.datetime) else str(self.timestamp)
        return (f"--- Block {self.index} ---\n"
                f"Timestamp: {ts_str}\n"
                f"Previous Hash: {self.previous_hash}\n"
                f"Data Signature: {self.signature}\n" # Display signature
                f"Block Hash: {self.hash}\n"
                f"Data: {json.dumps(self.data, indent=2, ensure_ascii=False)}\n"
                f"------------------\n")

# --- Blockchain Class ---
class MedicalBlockchain:
    def __init__(self):
        self.chain = []
        self.required_fields = [
            "patient_name", "session_date", "main_topics",
            "action_plan", "overall_assessment", "risk_assessment"
        ]
        self.all_fields = [
             "patient_name", "session_date", "main_topics",
             "patient_reported_mood", "physician_observations",
             "key_insights_or_progress", "action_plan",
             "risk_assessment", "overall_assessment"
        ]

    def _create_genesis_block(self):
        """Creates the first block in the chain with its data signature."""
        if not self.chain:
            genesis_data = {"type": "genesis", "info": "First Block - Signed"}
            genesis_signature = calculate_data_signature(genesis_data) # Calculate signature for genesis data
            genesis_block = Block(
                index=0,
                timestamp=datetime.datetime.now(datetime.timezone.utc), # Use timezone aware time
                data=genesis_data,
                signature=genesis_signature, # Add signature
                previous_hash="0"
            )
            self.chain.append(genesis_block)

    def get_latest_block(self):
        """Returns the most recent block in the chain."""
        if not self.chain:
            return None
        return self.chain[-1]

    def _validate_data(self, data):
        """Checks if the input data dictionary contains all required fields."""
        # (Validation logic remains the same)
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
        Adds a new block (medical record) to the chain after validation, including data signature.
        Returns True if successful, False otherwise.
        """
        if not self._validate_data(medical_data):
            print("Failed to add block due to invalid data.")
            return False

        if not self.chain:
            self._create_genesis_block()

        previous_block = self.get_latest_block()
        if previous_block is None:
            print("Error: Cannot add block, chain is unexpectedly empty.")
            return False

        new_index = previous_block.index + 1
        new_timestamp = datetime.datetime.now(datetime.timezone.utc) # Use timezone aware time
        new_signature = calculate_data_signature(medical_data) # Calculate signature for the new data

        new_block = Block(
            index=new_index,
            timestamp=new_timestamp,
            data=medical_data,
            signature=new_signature, # Pass the calculated signature
            previous_hash=previous_block.hash
            # hash_override is None, so hash will be calculated by Block.__init__
        )
        self.chain.append(new_block)
        print(f"Successfully added Block {new_index} with data signature.")
        return True

    def view_chain(self):
        # (Remains the same)
        if not self.chain:
            print("The blockchain is empty.")
            return
        print("\n--- Medical Record Blockchain ---")
        for block in self.chain:
            print(block) # __str__ now includes signature
        print("--- End of Blockchain ---\n")

    def view_previous_records(self, count=None):
        # (Remains the same, but output via __str__ will include signature)
        print("\n--- Viewing Previous Medical Records ---")
        records = self.chain[1:]
        if not records:
            print("No medical records found (only Genesis Block exists).")
            return []

        records_to_show = records[-count:] if count is not None and count > 0 else records
        print(f"(Showing {'last ' + str(len(records_to_show)) if count is not None and count > 0 else 'all ' + str(len(records_to_show))} records)")

        rtn = []
        for block in records_to_show:
             print(f"--- Record (Block {block.index}) ---")
             ts_str = block.timestamp.isoformat() if isinstance(block.timestamp, datetime.datetime) else str(block.timestamp)
             print(f"Timestamp: {ts_str}")
             print(f"Data Signature: {block.signature}") # Explicitly show signature here too
             print(f"Data:\n{json.dumps(block.data, indent=2, ensure_ascii=False)}")
             print(f"Block Hash: {block.hash}")
             print(f"Previous Hash: {block.previous_hash}")
             print("-" * 20)
             rtn.append(block.data)

        print("--- End of Records View ---\n")
        return rtn

    def is_chain_valid(self):
        """
        Validates the integrity of the blockchain, including data signatures.
        Checks:
        1. Data Integrity: If each block's data matches its signature.
        2. Block Hash Integrity: If each block's stored hash is correct based on its content (including signature).
        3. Chain Link Integrity: If each block correctly points to the previous block's hash.
        """
        if not self.chain:
            print("Blockchain is empty, cannot validate.")
            return True

        # Check Genesis block separately (basic checks)
        genesis_block = self.chain[0]
        if genesis_block.index != 0 or genesis_block.previous_hash != "0":
             print("Genesis block invalid (Index or Previous Hash).")
             return False
        if not genesis_block.is_data_valid():
             print(f"Genesis block data tampering detected! Signature mismatch.")
             print(f"  Stored Signature: {genesis_block.signature}")
             print(f"  Calculated Signature: {calculate_data_signature(genesis_block.data)}")
             return False
        if genesis_block.hash != genesis_block.calculate_hash():
             print(f"Genesis block hash mismatch! Stored: {genesis_block.hash}, Recalculated: {genesis_block.calculate_hash()}")
             return False


        # Check the rest of the chain
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # 1. Check Data Integrity using the signature
            if not current_block.is_data_valid():
                print(f"Data Tampering Detected: Block {current_block.index} data signature is invalid.")
                print(f"  Block Data: {json.dumps(current_block.data, sort_keys=True, ensure_ascii=False)}")
                print(f"  Stored Signature: {current_block.signature}")
                print(f"  Calculated Signature: {calculate_data_signature(current_block.data)}")
                return False

            # 2. Check Block Hash Integrity (Recalculate based on current content)
            #    This implicitly checks if the signature itself was tampered relative to the hash
            if current_block.hash != current_block.calculate_hash():
                print(f"Block Hash Mismatch or Tampering: Block {current_block.index} hash is invalid.")
                print(f"  Stored Hash: {current_block.hash}")
                print(f"  Recalculated Hash: {current_block.calculate_hash()}")
                # Optionally print details used for recalc:
                # print(f"  Data used for recalc: Index={current_block.index}, TS='{current_block.timestamp.isoformat()}', PrevHash='{current_block.previous_hash}', Sig='{current_block.signature}', Data='{json.dumps(current_block.data, sort_keys=True, ensure_ascii=False)}'")
                return False

            # 3. Check Chain Link Integrity
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain Broken: Block {current_block.index} previous_hash ({current_block.previous_hash}) does not match Block {previous_block.index} hash ({previous_block.hash}).")
                return False

        print("Blockchain integrity verified successfully (Data Signatures and Chain Links OK).")
        return True

    # --- File Operations ---
    def save_chain(self, filename=BLOCKCHAIN_FILE):
        """Saves the entire blockchain (including signatures) to a JSON file."""
        try:
            # Use block.to_dict which now includes the signature
            chain_data = [block.to_dict() for block in self.chain]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(chain_data, f, indent=4, ensure_ascii=False)
            print(f"Blockchain successfully saved to {filename}")
        except IOError as e:
            print(f"Error saving blockchain to {filename}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during saving: {e}")

    @classmethod
    def load_chain(cls, filename=BLOCKCHAIN_FILE):
        """Loads the blockchain (including signatures) from a JSON file."""
        new_blockchain = cls()
        if not os.path.exists(filename):
            print(f"Blockchain file '{filename}' not found. Starting a new chain with Genesis block.")
            new_blockchain._create_genesis_block()
            return new_blockchain

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)

            if not chain_data:
                 print(f"Blockchain file '{filename}' is empty. Starting a new chain with Genesis block.")
                 new_blockchain._create_genesis_block()
                 return new_blockchain

            # Reconstruct the chain using Block.from_dict which handles signature loading
            new_blockchain.chain = [Block.from_dict(block_data) for block_data in chain_data]
            print(f"Blockchain successfully loaded from {filename}. Contains {len(new_blockchain.chain)} blocks.")

            # IMPORTANT: Validate the loaded chain immediately to ensure integrity
            if not new_blockchain.is_chain_valid():
                 print("CRITICAL WARNING: Loaded blockchain failed integrity check! Data may be tampered or chain broken.")
                 # Decide policy: halt, warn, attempt repair? Warning is crucial here.
            else:
                 print("Loaded blockchain passed initial integrity check.")

            return new_blockchain

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {filename}: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain
        except KeyError as e:
             print(f"Error loading block data: Missing expected key '{e}'. File might be corrupted or from an older format.")
             print("Starting a new chain.")
             new_blockchain = cls() # Start fresh
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

# --- User Functions (Unchanged, but benefits from signature validation) ---

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
    my_medical_chain = MedicalBlockchain.load_chain() # load_chain now does validation
    print("-------------------------------------------\n")

    initial_record_count = len(my_medical_chain.chain) - 1 if len(my_medical_chain.chain) > 0 else 0
    print(f"Loaded chain has {initial_record_count} medical records (excluding Genesis).")

    if initial_record_count > 0:
         print("\n--- Viewing Records Loaded From File ---")
         view_all_previous_records(my_medical_chain)

    # --- Simulate Adding New Records ---
    print("\n--- Adding New Records ---")
    record_new_1 = {'main_topics': ['코딩 작업량 증가로 인한 스트레스', '수면 부족', '신앙적 어려움'], 'patient_name': '제리', 'action_plan': '매일 밤 잠들기 전 10분 기도', 'session_date': '2024-07-31', 'overall_assessment': '제리님은 최근 코딩 작업량 증가로 인해 스트레스와 수면 부족을 겪고 있으며, 신앙적인 어려움도 느끼고 있습니다. 규칙적인 수면 습관과 스트레스 해소 방법을 통해 개선할 필요가 있습니다.', 'risk_assessment': '없음', 'physician_observations': '피로한 모습, 불안한 표정', 'patient_reported_mood': '불안함'}
    input_medical_record(my_medical_chain, record_new_1)

    record_new_2 = { # Add another record for testing
      "patient_name": "테스트환자",
      "session_date": datetime.datetime.now().strftime("%Y-%m-%d"), # Use current date
      "main_topics": ["Signature Test", "Blockchain Integrity"],
      "patient_reported_mood": "궁금함",
      "physician_observations": "정상",
      "key_insights_or_progress": "Signature added and tested.",
      "action_plan": "Verify chain integrity.",
      "risk_assessment": "낮음",
      "overall_assessment": "Signature implementation successful."
    }
    input_medical_record(my_medical_chain, record_new_2)

    # --- View Records After Adding New Ones ---
    print("\n--- Viewing All Records (Including Newly Added) ---")
    view_all_previous_records(my_medical_chain)

    # --- Save the updated blockchain ---
    print("\n--- Saving Updated Blockchain ---")
    my_medical_chain.save_chain()

    # --- Tampering Simulation ---
    print("\n--- SIMULATING DATA TAMPERING in Block 1 (if exists) ---")
    if len(my_medical_chain.chain) > 1:
        block_to_tamper = my_medical_chain.chain[1] # Tamper the first *medical record* block
        original_data = json.loads(json.dumps(block_to_tamper.data)) # Deep copy
        original_signature = block_to_tamper.signature
        print(f"Original Data in Block 1: {json.dumps(original_data, ensure_ascii=False)}")
        print(f"Original Signature: {original_signature}")

        # Change the data *without* updating the signature
        block_to_tamper.data["patient_reported_mood"] = "!!!TAMPERED DATA!!!"
        block_to_tamper.data["risk_assessment"] = "!!!HIGH RISK!!!"
        print(f"Tampered Data in Block 1: {json.dumps(block_to_tamper.data, ensure_ascii=False)}")
        print(f"Signature remains: {block_to_tamper.signature}")

        print("\n--- Verifying Chain AFTER Tampering (EXPECT FAILURE) ---")
        my_medical_chain.is_chain_valid() # This should now fail the data signature check

        # --- Optional: Tamper signature as well ---
        # print("\n--- SIMULATING SIGNATURE TAMPERING in Block 1 ---")
        # block_to_tamper.data = original_data # Restore data
        # block_to_tamper.signature = "fakesignature123abc" # Change signature
        # print(f"Data restored, but signature tampered: {block_to_tamper.signature}")
        # print("--- Verifying Chain AFTER Signature Tampering (EXPECT FAILURE) ---")
        # my_medical_chain.is_chain_valid() # This should fail data signature check OR block hash check

        # --- Restore block for subsequent tests if needed ---
        # block_to_tamper.data = original_data
        # block_to_tamper.signature = original_signature
        # block_to_tamper.hash = block_to_tamper.calculate_hash() # Recalculate original hash too!

    else:
        print("Not enough blocks to perform tampering simulation.")


    # --- Final Integrity Check ---
    # Note: If tampering occurred and wasn't reverted, this will likely fail again.
    print("\n--- Performing Final Integrity Check ---")
    # Re-load from the saved file to ensure persistence works correctly
    print(f"--- Re-loading chain from {BLOCKCHAIN_FILE} ---")
    reloaded_chain = MedicalBlockchain.load_chain()
    print("\n--- Validating the Re-loaded Chain ---")
    reloaded_chain.is_chain_valid() # Should be valid if saved correctly and not tampered after load

    print("\n--- Script Finished ---")