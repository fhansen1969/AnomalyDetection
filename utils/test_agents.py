# test_agents_fixed.py
import yaml
import sys
import os

# Add the parent directory to the path to find anomaly_detection module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

print(f"Current dir: {current_dir}")
print(f"Parent dir: {parent_dir}")
print(f"sys.path[0]: {sys.path[0]}")

# First, let's see what files exist
agents_dir = os.path.join(parent_dir, 'anomaly_detection', 'agents')
if os.path.exists(agents_dir):
    print(f"\nFiles in {agents_dir}:")
    for file in os.listdir(agents_dir):
        if file.endswith('.py'):
            print(f"  - {file}")
else:
    print(f"\n✗ Agents directory not found at {agents_dir}")

# Try to import the agent manager
try:
    from anomaly_detection.agents.enhanced_agent_manager import EnhancedAgentManager
    print("\n✓ EnhancedAgentManager import successful")
    ENHANCED_AVAILABLE = True
except ImportError as e:
    print(f"\n✗ Failed to import EnhancedAgentManager: {e}")
    ENHANCED_AVAILABLE = False
    
try:
    from anomaly_detection.agents.agent_manager import AgentManager
    print("✓ Standard AgentManager import successful")
    STANDARD_AVAILABLE = True
except ImportError as e:
    print(f"✗ Failed to import AgentManager: {e}")
    STANDARD_AVAILABLE = False

if not STANDARD_AVAILABLE and not ENHANCED_AVAILABLE:
    print("\n✗ No agent managers available!")
    sys.exit(1)

# Load config
config_path = os.path.join(parent_dir, 'config', 'config.yaml')
print(f"\nLoading config from: {config_path}")
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

agents_config = config.get('agents', {})
print(f"Agent config: enabled={agents_config.get('enabled')}, use_enhanced={agents_config.get('use_enhanced')}")

# Try to create agent manager
try:
    use_enhanced = agents_config.get('use_enhanced', True) and ENHANCED_AVAILABLE
    
    if use_enhanced:
        print("\nTrying to create EnhancedAgentManager...")
        agent_manager = EnhancedAgentManager(agents_config, None)
        print("✓ EnhancedAgentManager created successfully")
    else:
        print("\nTrying to create standard AgentManager...")
        agent_manager = AgentManager(agents_config, None)
        print("✓ AgentManager created successfully")
except Exception as e:
    print(f"✗ Failed to create agent manager: {e}")
    import traceback
    traceback.print_exc()

try:
    # Note: agent_manager and config are populated at runtime by the API server's
    # lifespan handler, so they will be None when imported directly. We test the
    # import mechanism itself and use app_state for actual values.
    from api_services import get_default_agent_workflow
    from api.state import app_state

    print("1. Testing app_state.agent_manager:")
    print(f"   agent_manager is None: {app_state.agent_manager is None}")
    print(f"   agent_manager type: {type(app_state.agent_manager)}")

    print("\n2. Testing app_state.config:")
    print(f"   config is None: {app_state.config is None}")
    if app_state.config:
        print(f"   agents.enabled: {app_state.config.get('agents', {}).get('enabled', False)}")

    print("\n3. Testing get_default_agent_workflow:")
    print(f"   Is callable: {callable(get_default_agent_workflow)}")
    try:
        workflow = get_default_agent_workflow()
        print(f"   Workflow type: {type(workflow)}")
        print(f"   Workflow keys: {workflow.keys() if isinstance(workflow, dict) else 'Not a dict'}")
        if isinstance(workflow, dict) and "nodes" in workflow:
            print(f"   Nodes: {workflow['nodes']}")
    except Exception as e:
        print(f"   Error calling get_default_agent_workflow: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
