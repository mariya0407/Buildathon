import hashlib
import json
from datetime import datetime
import os  # New: For file persistence

class Block:
    def __init__(self, index, timestamp, data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.data = data  # Now: {"type": "post", "id": "id", "hash": "sha256_hash"} for anonymity
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": str(self.timestamp),
            "data": self.data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain_file = 'blockchain.json'  # New: Persist to file
        self.chain = self.load_chain() or [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, datetime.now(), {"type": "genesis", "hash": "0"}, "0")

    def load_chain(self):  # New: Load from JSON
        if os.path.exists(self.chain_file):
            with open(self.chain_file, 'r') as f:
                chain_data = json.load(f)
            return [Block(**block) for block in chain_data]
        return None

    def save_chain(self):  # New: Save to JSON
        with open(self.chain_file, 'w') as f:
            json.dump([block.__dict__ for block in self.chain], f, default=str)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, new_data):
        latest_block = self.get_latest_block()
        new_block = Block(
            index=latest_block.index + 1,
            timestamp=datetime.now(),
            data=new_data,
            previous_hash=latest_block.hash
        )
        self.chain.append(new_block)
        self.save_chain()  # Save after add
        return new_block

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            if current_block.hash != current_block.calculate_hash():
                print(f"Data integrity compromised at block {current_block.index}")
                return False
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain is broken at block {current_block.index}")
                return False
        return True

# Example Usage
if __name__ == '__main__':
    buildathon_chain = Blockchain()
    print("Adding block 1...")
    buildathon_chain.add_block({"type": "post", "id": 1, "hash": hashlib.sha256("This is the first post.".encode()).hexdigest()})
    
    print("Adding block 2...")
    buildathon_chain.add_block({"type": "post", "id": 2, "hash": hashlib.sha256("Second post content.".encode()).hexdigest()})

    for block in buildathon_chain.chain:
        print(json.dumps(block.__dict__, indent=4, sort_keys=True, default=str))

    print(f"\nIs blockchain valid? {buildathon_chain.is_chain_valid()}")