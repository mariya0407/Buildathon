import hashlib
import time
import json

class Blockchain:
    def __init__(self):
        # Initialize chain with genesis block
        self.chain = [self.create_genesis_block()]
        self.difficulty = 2  # Proof-of-work difficulty (light for dev)

    def create_genesis_block(self):
        # First block in the chain
        return {
            "index": 0,
            "timestamp": time.time(),
            "data": {"message": "Genesis Block"},
            "previous_hash": "0",
            "hash": self.calculate_hash(0, time.time(), {"message": "Genesis Block"}, "0")
        }

    def calculate_hash(self, index, timestamp, data, previous_hash):
        # Create SHA-256 hash for a block
        block_string = json.dumps({
            "index": index,
            "timestamp": timestamp,
            "data": data,
            "previous_hash": previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def add_block(self, data):
        # Add a new block with user/post data
        previous_block = self.chain[-1]
        index = previous_block["index"] + 1
        timestamp = time.time()
        block = {
            "index": index,
            "timestamp": timestamp,
            "data": data,  # E.g., {"user_id": "...", "user_hash": "..."} or {"post_id": "...", "post_hash": "..."}
            "previous_hash": previous_block["hash"]
        }
        block["hash"] = self.calculate_hash(index, timestamp, data, previous_block["hash"])
        self.chain.append(block)
        return block

    def is_chain_valid(self):
        # Verify chain integrity
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            if current["hash"] != self.calculate_hash(
                current["index"], current["timestamp"], current["data"], current["previous_hash"]
            ):
                return False
            if current["previous_hash"] != previous["hash"]:
                return False
        return True

# Instantiate the blockchain
blockchain = Blockchain()