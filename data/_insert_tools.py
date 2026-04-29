import os

# Read agent.py
with open("agent.py", "r", encoding="utf-8") as f:
    content = f.read()

# Read new tools
with open(os.path.join("data", "_new_tools.txt"), "r", encoding="utf-8") as f:
    new_tools = f.read()

# Find the spot: after "Erro no VS Code" line, before "# ENTRYPOINT"
marker = 'return f"Erro no VS Code: {e}"'
idx = content.find(marker)

if idx == -1:
    print("ERROR: Could not find VS Code error marker")
    exit(1)

# Move past the marker to end of that line
end_of_line = content.index("\n", idx)

# Find the ENTRYPOINT section
entrypoint_marker = "# ENTRYPOINT"
ep_idx = content.find(entrypoint_marker, end_of_line)

if ep_idx == -1:
    print("ERROR: Could not find ENTRYPOINT marker")
    exit(1)

# Find the "# ─────" line before ENTRYPOINT
dash_line_start = content.rfind("# ", end_of_line, ep_idx)
# Go to the beginning of that line
while dash_line_start > 0 and content[dash_line_start - 1] not in "\r\n":
    dash_line_start -= 1

# Build new content
new_content = content[:end_of_line + 1] + new_tools + "\n" + content[dash_line_start:]

with open("agent.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("SUCCESS: New tools inserted into agent.py")
print(f"  - Marker found at: {idx}")
print(f"  - ENTRYPOINT found at: {ep_idx}")
print(f"  - New tools size: {len(new_tools)} chars")
