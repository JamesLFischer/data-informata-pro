// Public config only - no secrets. The channel name is not a secret: without the password nothing on it can be read or forged.
window.AIVIS_RELAY = {ntfy: "https://ntfy.sh", channel: "sdm-aeo-c3bf3ba70a6eb508376e48e9"};
// Optional direct API (aivis.server behind an HTTPS tunnel). Leave "" to use the encrypted relay.
window.AIVIS_API_BASE = "";
