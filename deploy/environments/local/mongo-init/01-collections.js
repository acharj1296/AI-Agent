// MongoDB init script (runs once on the first database start, when the data volume is empty).
// Creates the MVP collection set for the AI-Agent project, matching db/indexes.py.
// The application also ensures collections + indexes at startup (python -m aiagent.db),
// so this script is only a first-boot convenience for standalone Mongo use.

db = db.getSiblingDB("aiagent");

var collections = [
  "organizations",
  "users",
  "projects",
  "agents",
  "agent_runs",
  "tasks",
  "workflow_runs",
  "artifacts",
  "messages",
  "memories",
  "approvals",
  "reviews",
  "tool_calls",
  "models",
  "events",
  "audit_logs",
];

var created = [];
collections.forEach(function (name) {
  if (!db.getCollectionNames().includes(name)) {
    db.createCollection(name);
    created.push(name);
  }
});

print("MongoDB collections created: " + (created.join(", ") || "none (all existed)"));