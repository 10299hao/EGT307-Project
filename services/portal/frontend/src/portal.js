/** Shared dashboard configuration, formatting helpers and API client. */

export const EMPTY_STATS = {
  total_incidents: 0,
  open_incidents: 0,
  critical_open: 0,
  completed_actions: 0,
  average_confidence: 0,
  by_severity: {},
};

export const EMPTY_SERVICES = {
  portal: "checking",
  database: "checking",
  redis: "checking",
  collector: "checking",
  analyzer: "checking",
  executor: "checking",
  integration_bridge: "checking",
  local_notifications: "checking",
  mode: "checking",
  data_source: "checking",
  incident_stream: "IncidentStream",
  action_request_stream: "ActionStream",
  action_request_field: "command",
  action_result_stream: "action-results",
  dead_letter_stream: "portal-dead-letter",
  collector_output_stream: "log-events",
  collector_message_field: "data",
  analyzer_input_stream: "LogStream",
  analyzer_message_field: "payload",
};

export const VIEW_COPY = {
  overview: ["Operations overview", "Monitor current HDFS incidents and automated responses."],
  incidents: ["Incident queue", "Investigate model results, evidence and executor actions."],
  activity: ["Activity history", "Follow each incident from detection to operator acknowledgement."],
  system: ["System status", "Check the health and connection of each project component."],
};

export const titleCase = (text = "") =>
  text.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export const percent = (value = 0) =>
  `${(value * 100).toFixed(value > 0.99 ? 2 : 1)}%`;

export const formatTime = (value) => new Intl.DateTimeFormat("en-SG", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
}).format(new Date(value));

export async function getJson(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`Request failed with ${response.status}`);
  return response.json();
}
