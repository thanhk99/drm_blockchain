import sys
import os
sys.path.append(os.getcwd())

from core.config_loader import load_config
from engines.blockchain.blockchain_manager import BlockchainManager

def test_node_creation():
    config = load_config("config.yaml")
    
    # 1. Create a node for Alice
    print("--- Testing Node Creation for Alice ---")
    alice_bm = BlockchainManager(config, node_name="Alice")
    assert alice_bm.node_name == "Alice"
    assert os.path.exists("nodes/Alice/ledger.json")
    assert os.path.exists("nodes/Alice/keys/private.pem")
    print("Alice node created successfully.")
    
    # 2. Register copyright in Alice node
    print("\n--- Registering Copyright in Alice Node ---")
    success, msg = alice_bm.register_copyright(["hash123"], "phash123", "whash123", {"orb": "data"}, "Alice")
    assert success is True
    print("Alice registration successful.")
    
    # 3. Verify integrity
    assert alice_bm.is_chain_valid() is True
    print("Alice ledger integrity verified.")
    
    # 4. Global search simulation
    print("\n--- Global Search Verification ---")
    all_nodes = BlockchainManager.list_all_nodes()
    print(f"Nodes found: {all_nodes}")
    assert "Alice" in all_nodes
    
    # Test verifying from another node instance (like the System node)
    system_bm = BlockchainManager(config, node_name="System")
    found, record, match_type = system_bm.verify_copyright("hash123")
    assert found is False # Should not find it in 'System' ledger
    
    # Simulate the global scan logic from main.py
    found_globally = False
    for node in all_nodes:
        temp_bm = BlockchainManager(config, node_name=node)
        found, record, match_type = temp_bm.verify_copyright("hash123")
        if found:
            print(f"Found record globally in node: {node}")
            found_globally = True
            break
    assert found_globally is True
    print("Global verification test passed.")

if __name__ == "__main__":
    test_node_creation()
