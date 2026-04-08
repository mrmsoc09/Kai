cd /home/k1-admin/Kai

# Test 1: Verify the three tools are executable and functional
testssl.sh --version
spiderfoot --version
graphql-cop --version

# Test 2: Check that the bootstrap functions file exists and can be sourced
source scripts/tools-bootstrap-functions.sh && echo "Bootstrap functions sourced successfully"

# Test 3: Verify setup.sh can be sourced (check for syntax errors during sourcing)
source scripts/setup.sh 2>&1 | head -20

# Test 4: Verify tool registry has the Wave 7 entries
grep -A 5 "name: testssl" tools/registry/tool_registry.yaml
grep -A 5 "name: spiderfoot" tools/registry/tool_registry.yaml
grep -A 5 "name: graphql-cop" tools/registry/tool_registry.yaml

