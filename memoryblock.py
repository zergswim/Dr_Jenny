import hashlib
import datetime
import json
import os
import asyncio

# --- Constants ---
AGENT_MEMORY_BLOCKCHAIN_FILE = "agent_memory_blockchain.json"
AGENT_ID_FIELD = "agent_id"
MEMORY_PAYLOAD_FIELD = "memory_payload"

# --- Signature Helper Function (Unchanged) ---
def calculate_data_signature(data):
    data_string = json.dumps(data, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(data_string).hexdigest()

# --- Block Class (Essentially Unchanged, but used for Agent Memory) ---
class Block:
    def __init__(self, index, timestamp, data, signature, previous_hash, hash_override=None):
        self.index = index
        # Ensure timestamp is a datetime object (Handles loading from ISO string)
        if isinstance(timestamp, str):
            try:
                # Handle potential timezone info ('Z' or '+HH:MM')
                if timestamp.endswith('Z'):
                    timestamp = timestamp[:-1] + '+00:00'
                self.timestamp = datetime.datetime.fromisoformat(timestamp)
            except ValueError:
                print(f"Warning: Could not parse timestamp string '{timestamp}'. Using current UTC time.")
                self.timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        elif isinstance(timestamp, datetime.datetime):
            if timestamp.tzinfo is None: # Make naive timezone aware (assume UTC)
                 timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
            self.timestamp = timestamp.replace(microsecond=0) # Remove microseconds for consistency
        else:
            print(f"Warning: Invalid timestamp type ({type(timestamp)}). Using current UTC time.")
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

        self.data = data # Agent memory state dictionary
        self.signature = signature # Data integrity signature
        self.previous_hash = previous_hash
        self.hash = hash_override if hash_override is not None else self.calculate_hash()

    def calculate_hash(self):
        block_string = str(self.index) + \
                       self.timestamp.isoformat() + \
                       json.dumps(self.data, sort_keys=True, ensure_ascii=False) + \
                       str(self.signature) + \
                       str(self.previous_hash)
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

    def is_data_valid(self):
        """Verifies if the stored data matches its signature."""
        return self.signature == calculate_data_signature(self.data)

    def to_dict(self):
        """Converts the Block object to a JSON-serializable dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(), # Store as ISO string (UTC)
            "data": self.data,
            "signature": self.signature,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, block_dict):
        """Creates a Block instance from a dictionary (loaded from JSON)."""
        signature = block_dict.get('signature')
        if signature is None:
             # This should ideally not happen if saved correctly, but handle it
             print(f"Warning: Block {block_dict.get('index', 'N/A')} loaded without a signature. Calculating now.")
             signature = calculate_data_signature(block_dict['data'])

        return cls(
            index=block_dict['index'],
            timestamp=block_dict['timestamp'], # Parsed in __init__
            data=block_dict['data'],
            signature=signature,
            previous_hash=block_dict['previous_hash'],
            hash_override=block_dict['hash'] # Preserve original hash
        )

    def __str__(self):
        """String representation of the block for printing."""
        ts_str = self.timestamp.isoformat()
        return (f"--- Block {self.index} ---\n"
                f"Timestamp: {ts_str}\n"
                f"Previous Hash: {self.previous_hash}\n"
                f"Data Signature: {self.signature}\n"
                f"Block Hash: {self.hash}\n"
                f"Data: {json.dumps(self.data, indent=2, ensure_ascii=False)}\n"
                f"------------------\n")

# --- Agent Memory Blockchain Class ---
class AgentMemoryBlockchain:
    def __init__(self):
        self.chain = []
        # Required fields for a memory record
        self.required_memory_fields = [AGENT_ID_FIELD, MEMORY_PAYLOAD_FIELD]

    def _create_genesis_block(self):
        """Creates the first block (Genesis Block)."""
        if not self.chain:
            genesis_data = {"type": "genesis_agent_memory", "info": "Agent Memory Chain Start"}
            genesis_signature = calculate_data_signature(genesis_data)
            genesis_block = Block(
                index=0,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                data=genesis_data,
                signature=genesis_signature,
                previous_hash="0"
            )
            self.chain.append(genesis_block)
            print("Genesis block created for Agent Memory Blockchain.")

    def get_latest_block(self):
        """Returns the most recent block in the chain."""
        if not self.chain:
            return None
        return self.chain[-1]

    def _validate_memory_data(self, memory_data):
        """Checks if the input memory data dictionary is valid."""
        if not isinstance(memory_data, dict):
            print("Error: Input memory data must be a dictionary.")
            return False
        missing_required = [field for field in self.required_memory_fields if field not in memory_data]
        if missing_required:
            print(f"Error: Missing required memory fields: {', '.join(missing_required)}")
            return False
        # Optional: Add type checks for payload if needed (e.g., must be dict/list)
        # if not isinstance(memory_data.get(MEMORY_PAYLOAD_FIELD), (dict, list)):
        #    print(f"Error: '{MEMORY_PAYLOAD_FIELD}' must be a dictionary or list.")
        #    return False
        return True

    def record_memory(self, agent_id, memory_payload, context_summary=None, current_goal=None, session_id=None):
        """
        Records the agent's current memory state onto the blockchain.

        Args:
            agent_id (str): The unique identifier for the agent.
            memory_payload (any): The JSON-serializable data representing the agent's memory
                                  (e.g., dict, list, string).
            context_summary (str, optional): A brief description of the current context.
            current_goal (str, optional): The agent's current objective.
            session_id (str, optional): Identifier for the current session/interaction.

        Returns:
            bool: True if the memory was successfully recorded, False otherwise.
        """
        memory_data = {
            AGENT_ID_FIELD: agent_id,
            "timestamp_saved": datetime.datetime.now(datetime.timezone.utc).isoformat(), # Record save time in data too
            MEMORY_PAYLOAD_FIELD: memory_payload,
            "context_summary": context_summary,
            "current_goal": current_goal,
            "session_id": session_id
        }
        # Filter out optional fields that are None
        memory_data = {k: v for k, v in memory_data.items() if v is not None}

        if not self._validate_memory_data(memory_data):
            print("Failed to record memory due to invalid data.")
            return False

        if not self.chain:
            self._create_genesis_block()

        previous_block = self.get_latest_block()
        if previous_block is None:
            print("Error: Cannot record memory, chain is unexpectedly empty after genesis check.")
            return False

        new_index = previous_block.index + 1
        # Use block timestamp primarily, included saved timestamp in data for reference
        new_timestamp = datetime.datetime.now(datetime.timezone.utc)
        new_signature = calculate_data_signature(memory_data) # Signature of the memory data itself

        new_block = Block(
            index=new_index,
            timestamp=new_timestamp,
            data=memory_data,
            signature=new_signature,
            previous_hash=previous_block.hash
        )
        self.chain.append(new_block)
        print(f"Successfully recorded memory for Agent '{agent_id}' in Block {new_index}.")
        return True

    def recall_latest_memory(self, agent_id):
        """
        Retrieves the latest valid memory payload for the specified agent.

        Args:
            agent_id (str): The unique identifier for the agent whose memory is needed.

        Returns:
            any: The latest memory payload if found and valid, otherwise None.
        """
        if not self.chain or len(self.chain) <= 1:
            print(f"No memory records found for Agent '{agent_id}' (chain empty or only Genesis).")
            return None

        print(f"Searching for latest valid memory for Agent '{agent_id}'...")
        # Iterate backwards from the newest block (excluding Genesis)
        for block in reversed(self.chain[1:]):
            if isinstance(block.data, dict) and block.data.get(AGENT_ID_FIELD) == agent_id:
                print(f"Found potential record in Block {block.index} for Agent '{agent_id}'. Verifying...")
                # 1. Verify data integrity using the signature stored within the block
                if not block.is_data_valid():
                    print(f"Warning: Data tampering detected in Block {block.index} for Agent '{agent_id}'. Skipping.")
                    continue # Skip this block, look for the next older one

                # 2. (Implicitly checked by is_chain_valid, but good practice)
                #    Verify block hash integrity (optional here if is_chain_valid is used elsewhere)
                # if block.hash != block.calculate_hash():
                #    print(f"Warning: Block hash mismatch in Block {block.index}. Skipping.")
                #    continue

                # If data is valid, this is the latest valid memory for this agent
                print(f"Found valid memory in Block {block.index}. Recalling payload.")
                return block.data.get(MEMORY_PAYLOAD_FIELD)

        print(f"No valid memory records found for Agent '{agent_id}' after checking the chain.")
        return None

    def is_chain_valid(self):
        """Validates the entire blockchain integrity (Unchanged logic, crucial for trust)."""
        if not self.chain:
            print("Blockchain is empty, cannot validate.")
            return True # An empty chain is trivially valid

        # Check Genesis block separately
        genesis_block = self.chain[0]
        if genesis_block.index != 0 or genesis_block.previous_hash != "0":
             print("Genesis block invalid (Index or Previous Hash).")
             return False
        if not genesis_block.is_data_valid(): # Check data signature
             print(f"Genesis block data tampering detected! Signature mismatch.")
             return False
        if genesis_block.hash != genesis_block.calculate_hash(): # Check block hash
             print(f"Genesis block hash mismatch!")
             return False

        # Check the rest of the chain
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # 1. Check Data Integrity using the signature
            if not current_block.is_data_valid():
                print(f"Data Tampering Detected: Block {current_block.index} data signature is invalid.")
                return False

            # 2. Check Block Hash Integrity
            if current_block.hash != current_block.calculate_hash():
                print(f"Block Hash Mismatch or Tampering: Block {current_block.index} hash is invalid.")
                return False

            # 3. Check Chain Link Integrity
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain Broken: Block {current_block.index} previous_hash does not match Block {previous_block.index} hash.")
                return False

        print("Agent Memory Blockchain integrity verified successfully.")
        return True

    # --- File Operations (Adapted for Agent Memory) ---
    def save_chain(self, filename=AGENT_MEMORY_BLOCKCHAIN_FILE):
        """Saves the agent memory blockchain to a JSON file."""
        try:
            chain_data = [block.to_dict() for block in self.chain]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(chain_data, f, indent=4, ensure_ascii=False)
            print(f"Agent Memory Blockchain successfully saved to {filename}")
        except IOError as e:
            print(f"Error saving blockchain to {filename}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during saving: {e}")

    @classmethod
    def load_chain(cls, filename=AGENT_MEMORY_BLOCKCHAIN_FILE):
        """Loads the agent memory blockchain from a JSON file."""
        new_blockchain = cls() # Create an instance of AgentMemoryBlockchain
        if not os.path.exists(filename):
            print(f"Blockchain file '{filename}' not found. Creating a new chain with Genesis block.")
            new_blockchain._create_genesis_block() # Initialize with Genesis
            return new_blockchain

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                chain_data = json.load(f)

            if not chain_data:
                 print(f"Blockchain file '{filename}' is empty. Creating a new chain with Genesis block.")
                 new_blockchain._create_genesis_block()
                 return new_blockchain

            # Reconstruct the chain using Block.from_dict
            new_blockchain.chain = [Block.from_dict(block_data) for block_data in chain_data]
            print(f"Agent Memory Blockchain loaded from {filename}. Contains {len(new_blockchain.chain)} blocks.")

            # Immediately validate the loaded chain
            if not new_blockchain.is_chain_valid():
                 print("CRITICAL WARNING: Loaded agent memory blockchain failed integrity check!")
            else:
                 print("Loaded agent memory blockchain passed initial integrity check.")

            return new_blockchain

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {filename}: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain
        except KeyError as e:
             print(f"Error loading block data: Missing expected key '{e}'. File might be corrupted.")
             print("Starting a new chain.")
             new_blockchain = cls()
             new_blockchain._create_genesis_block()
             return new_blockchain
        except Exception as e:
            print(f"An unexpected error occurred during loading: {e}. Starting a new chain.")
            new_blockchain._create_genesis_block()
            return new_blockchain

    def view_chain_history(self, agent_id=None):
        """Prints the history, optionally filtered by agent_id."""
        if not self.chain:
            print("The agent memory blockchain is empty.")
            return

        print(f"\n--- Agent Memory Blockchain History (Agent: {agent_id if agent_id else 'All'}) ---")
        filtered_blocks = 0
        total_blocks = 0
        for block in self.chain:
             total_blocks += 1
             if agent_id is None or (isinstance(block.data, dict) and block.data.get(AGENT_ID_FIELD) == agent_id) or block.index == 0: # Show Genesis too
                 print(block)
                 filtered_blocks +=1

        if agent_id and filtered_blocks <= 1 : # Only Genesis found
             print(f"No specific memory records found for Agent ID: {agent_id}")
        print(f"--- End of History (Showing {filtered_blocks}/{total_blocks} Blocks) ---\n")


# memory_chain = AgentMemoryBlockchain.load_chain()
# agent_id = "Dr.Jenny"

# async def record_agent_memory(args):
#     # function calling 호출용
#     print("[DEBUG] init. memory_chain", memory_chain)
#     # print(type(args), args)
#     args = dict(args)
#     # print(type(args), args)
#     memory_chain.record_memory(    
#         agent_id=agent_id,
#         memory_payload=args["memory_payload"],
#         context_summary=args["context_summary"],
#         current_goal=args["current_goal"],
#         session_id=args["current_goal"]
#     )
#     return "ok"
#     # 튕금.. 방지법은?
#     #await asyncio.to_thread(memory_chain.save_chain())

# async def recall_agent_memory(args):
#     # print(args)
#     return memory_chain.recall_latest_memory(agent_id)

# Definition for recording agent memory
record_agent_memory_json = {
    "name": "record_agent_memory",
    "description": "AI 에이전트의 현재 메모리 상태(중요 데이터, 컨텍스트, 목표 등)를 안전한 블록체인에 기록합니다. 메모리 리셋 후 복구를 위해 사용됩니다. (Records the AI agent's current memory state (critical data, context, goals, etc.) onto the secure blockchain. Used for recovery after memory resets.)",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "메모리를 기록하는 AI 에이전트의 고유 식별자입니다. (The unique identifier of the AI agent recording the memory.)"
            },
            "memory_payload": {
                # Using 'object' allows flexibility (dict, list, etc.)
                # If you know it will ALWAYS be a dictionary, you can keep 'object'.
                # If it might sometimes be a simple string or number, using just 'string' or 'number'
                # might be too restrictive. 'object' generally works well for complex state.
                "type": "object", # Or potentially "string" if payload is always simple text
                "description": """JSON 직렬화 가능한 에이전트의 핵심 메모리 데이터입니다. 딕셔너리 형태가 일반적입니다. (The agent's core memory data, which must be JSON-serializable. Typically a dictionary.)
                                예시: {"last_task": "...", "learned_info": [...], "user_prefs": {...}}"""
            },
            "context_summary": {
                "type": "string",
                "description": "(선택사항) 현재 작업 또는 대화의 맥락 요약. (Optional: A summary of the current task or conversation context.)"
            },
            "current_goal": {
                "type": "string",
                "description": "(선택사항) 에이전트가 현재 추구하고 있는 목표. (Optional: The goal the agent is currently pursuing.)"
            },
            "session_id": {
                "type": "string",
                "description": "(선택사항) 현재 상호작용 세션을 식별하는 ID. (Optional: An ID to identify the current interaction session.)"
            }
        },
        "required": [
            "agent_id",
            "memory_payload"
        ]
    }
}

# Definition for recalling agent memory
recall_agent_memory_json = {
    "name": "recall_agent_memory",
    "description": "지정된 AI 에이전트의 가장 최근 유효한 메모리 상태를 블록체인에서 불러옵니다. 에이전트 재시작 또는 리셋 시 사용됩니다. (Retrieves the most recent valid memory state for the specified AI agent from the blockchain. Used upon agent restart or reset.)",
    "parameters": {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "메모리를 불러올 AI 에이전트의 고유 식별자입니다. (The unique identifier of the AI agent whose memory needs to be recalled.)"
            }
        },
        "required": [
            "agent_id"
        ]
    }
}

async def main():
    args = {'memory_payload': {'user_prefs': {'music': 'classical', 'light': 'dim'}, 'last_task': 'function calling test'}, 'agent_id': 'jerry_agent', 'session_id': 'session_123', 'context_summary': 'Testing record_agent_memory function', 'current_goal': 'Successfully record agent memory'}
    await record_agent_memory(args)

# --- Example Agent Simulation ---
if __name__ == "__main__":

    asyncio.run(main())
     # # 1. Load or create the blockchain
    # print(f"--- Loading Agent Memory Blockchain ({AGENT_MEMORY_BLOCKCHAIN_FILE}) ---")
    # memory_chain = AgentMemoryBlockchain.load_chain()
    # print("-" * 30)

    # # --- Agent Simulation ---
    # agent_id_1 = "AI_Assistant_007"
    # agent_id_2 = "Data_Analyzer_42"

    # # Simulate Agent 1 saving memory before reset
    # print(f"\n--- Agent {agent_id_1} recording memory ---")
    # memory_state_1 = {
    #     "last_interaction": "User asked about weather in Seoul",
    #     "user_preferences": {"units": "celsius", "location": "Seoul"},
    #     "learned_facts": ["Seoul is the capital of South Korea"],
    #     "conversation_turns": 15
    # }
    # memory_chain.record_memory(
    #     agent_id=agent_id_1,
    #     memory_payload=memory_state_1,
    #     context_summary="Weather Inquiry",
    #     current_goal="Provide accurate weather forecast",
    #     session_id="session_abc123"
    # )

    # # Simulate Agent 2 saving memory
    # print(f"\n--- Agent {agent_id_2} recording memory ---")
    # memory_state_2 = {
    #     "dataset_loaded": "sales_data_q3.csv",
    #     "analysis_progress": "Generated initial statistics",
    #     "pending_visualizations": ["Sales trend", "Regional breakdown"],
    #     "key_findings": []
    # }
    # memory_chain.record_memory(
    #     agent_id=agent_id_2,
    #     memory_payload=memory_state_2,
    #     context_summary="Sales Data Analysis",
    #     current_goal="Identify sales trends"
    # )

    # # Simulate Agent 1 saving MORE memory later
    # print(f"\n--- Agent {agent_id_1} recording updated memory ---")
    # memory_state_1_updated = {
    #     "last_interaction": "User asked for a 3-day forecast",
    #     "user_preferences": {"units": "celsius", "location": "Seoul"},
    #     "learned_facts": ["Seoul is the capital of South Korea", "User prefers short forecasts"],
    #     "conversation_turns": 25 # Updated value
    # }
    # memory_chain.record_memory(
    #     agent_id=agent_id_1,
    #     memory_payload=memory_state_1_updated,
    #     context_summary="Weather Inquiry - Follow-up",
    #     current_goal="Provide 3-day weather forecast",
    #     session_id="session_abc123" # Same session
    # )
    # print("-" * 30)

    # # --- Agent Restart Simulation ---
    # print("\n--- SIMULATING AGENT RESTART ---")

    # # Agent 1 restarts and needs its memory
    # print(f"\n--- Agent {agent_id_1} attempting to recall memory ---")
    # recalled_memory_1 = memory_chain.recall_latest_memory(agent_id_1)
    # if recalled_memory_1:
    #     print(f"\nAgent {agent_id_1} successfully recalled memory:")
    #     print(json.dumps(recalled_memory_1, indent=2, ensure_ascii=False))
    #     # Agent can now re-initialize its state using recalled_memory_1
    #     assert recalled_memory_1["conversation_turns"] == 25 # Verify latest was retrieved
    # else:
    #     print(f"Agent {agent_id_1} could not find previous memory.")

    # # Agent 2 restarts and needs its memory
    # print(f"\n--- Agent {agent_id_2} attempting to recall memory ---")
    # recalled_memory_2 = memory_chain.recall_latest_memory(agent_id_2)
    # if recalled_memory_2:
    #     print(f"\nAgent {agent_id_2} successfully recalled memory:")
    #     print(json.dumps(recalled_memory_2, indent=2, ensure_ascii=False))
    #     # Agent can now re-initialize its state using recalled_memory_2
    #     assert recalled_memory_2["dataset_loaded"] == "sales_data_q3.csv"
    # else:
    #     print(f"Agent {agent_id_2} could not find previous memory.")

    # # Agent 3 (non-existent) tries to recall
    # print(f"\n--- Agent 'Unknown_Agent_99' attempting to recall memory ---")
    # recalled_memory_3 = memory_chain.recall_latest_memory("Unknown_Agent_99")
    # if not recalled_memory_3:
    #     print("As expected, no memory found for Unknown_Agent_99.")
    # print("-" * 30)

    # # --- View History ---
    # # memory_chain.view_chain_history() # View all
    # memory_chain.view_chain_history(agent_id=agent_id_1) # View history for Agent 1

    # # --- Save the updated blockchain ---
    # print("\n--- Saving Agent Memory Blockchain ---")
    # memory_chain.save_chain()

    # # --- Final Integrity Check ---
    # print("\n--- Performing Final Integrity Check on Saved Chain ---")
    # reloaded_chain = AgentMemoryBlockchain.load_chain()
    # reloaded_chain.is_chain_valid()

    # print("\n--- Agent Memory Simulation Finished ---")