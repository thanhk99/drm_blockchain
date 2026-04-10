import sys
import os
sys.path.append(os.getcwd())

from core.config_loader import load_config
from engines.blockchain.blockchain_manager import BlockchainManager

def test_synchronized_network():
    config = load_config("config.yaml")
    
    # Ensure nodes dir is clean for test (optional, already cleared by Phase 6)
    
    print("--- 1. Initializing Nodes for Alice and Bob ---")
    alice_bm = BlockchainManager(config, node_name="Alice")
    bob_bm = BlockchainManager(config, node_name="Bob")
    
    assert alice_bm.node_name == "Alice"
    assert bob_bm.node_name == "Bob"
    print("Nodes initialized.")

    print("\n--- 2. Alice registers a copyright ---")
    # Alice registers something. This should trigger a broadcast to Bob.
    success, msg = alice_bm.register_copyright(["alice_image_hash"], "p123", "w123", {"feature": "xyz"}, "Alice")
    assert success is True
    print("Alice registered copyright and broadcasted block.")

    print("\n--- 3. Verifying Bob's Synchronized Ledger ---")
    # Reload Bob's ledger to see the change (though broadcast_block already updated it)
    bob_bm_reloaded = BlockchainManager(config, node_name="Bob")
    
    # Bob should have 2 blocks now: Genesis and Alice's block
    ledger = bob_bm_reloaded.ledger
    print(f"Bob's ledger size: {len(ledger)}")
    assert len(ledger) == 2
    
    alice_block = ledger[1]
    print(f"Block 1 owner: {alice_block['owner']}")
    assert alice_block["owner"] == "Alice"
    
    # Bob verifies the chain integrity (including Alice's signature)
    is_valid = bob_bm_reloaded.is_chain_valid()
    print(f"Bob verifies chain integrity: {is_valid}")
    assert is_valid is True
    print("Bob successfully verified Alice's block signature in his own ledger.")

    print("\n--- 4. Tampering Test ---")
    # Simulate a hacker modifying Alice's block in Bob's ledger
    alice_block["nonce"] = 999999 
    # Bob's integrity check should now fail
    is_valid_after_tamper = bob_bm_reloaded.is_chain_valid()
    print(f"Bob verifies chain after tampering: {is_valid_after_tamper}")
    assert is_valid_after_tamper is False
    print("Tampering detected successfully!")

    print("\nSUCCESS: All synchronization tests passed.")

if __name__ == "__main__":
    test_synchronized_network()
