import hashlib
import json
from datetime import datetime

class Block:
    """
    Represents a single block in our blockchain.
    """
    def __init__(self, index, timestamp, data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.data = data # e.g., a post, a comment, an upvote
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        """
        Calculates the SHA-256 hash of the block's contents.
        """
        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps({
            "index": self.index,
            "timestamp": str(self.timestamp),
            "data": self.data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    """
    Manages the chain of blocks.
    """
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        """
        Creates the very first block in the chain, manually.
        """
        return Block(0, datetime.now(), "Genesis Block", "0")

    def get_latest_block(self):
        """
        Returns the most recent block in the chain.
        """
        return self.chain[-1]

    def add_block(self, new_data):
        """
        Creates a new block, links it to the chain, and adds it.
        """
        latest_block = self.get_latest_block()
        new_block = Block(
            index=latest_block.index + 1,
            timestamp=datetime.now(),
            data=new_data,
            previous_hash=latest_block.hash
        )
        self.chain.append(new_block)
        return new_block

    def is_chain_valid(self):
        """
        Validates the integrity of the blockchain.
        Checks if each block's hash is correct and linked to the previous one.
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # Check if the hash of the block is correct
            if current_block.hash != current_block.calculate_hash():
                print(f"Data integrity compromised at block {current_block.index}")
                return False
            
            # Check if the block is correctly linked to the previous block
            if current_block.previous_hash != previous_block.hash:
                print(f"Chain is broken at block {current_block.index}")
                return False
        
        return True

# --- Example Usage (for testing purposes) ---
if __name__ == '__main__':
    # Create a new blockchain
    buildathon_chain = Blockchain()

    # Add some blocks (representing posts)
    print("Adding block 1...")
    buildathon_chain.add_block({"post_id": 1, "content": "This is the first post.", "author": "anon1"})
    
    print("Adding block 2...")
    buildathon_chain.add_block({"post_id": 2, "content": "Second post content.", "author": "anon2"})

    # Print the chain
    for block in buildathon_chain.chain:
        print(json.dumps(block.__dict__, indent=4, sort_keys=True, default=str))

    # Validate the chain
    print(f"\nIs blockchain valid? {buildathon_chain.is_chain_valid()}")
