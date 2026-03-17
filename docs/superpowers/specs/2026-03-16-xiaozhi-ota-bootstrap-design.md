# Xiaozhi OTA Bootstrap Design

## Goal

Update the Python client so it follows Xiaozhi's device bootstrap flow before opening the WebSocket audio channel.

## Scope

- Request OTA/bootstrap metadata before any WebSocket connection.
- Persist a valid `client_id` locally and reuse it across runs.
- Detect activation-required responses and print the activation code, then exit cleanly.
- Reuse the returned WebSocket URL and token for the existing audio interaction flow.

## Design

The client keeps `device_id` as the device identity but no longer assumes the WebSocket URL and token are static. On startup it resolves a persistent UUID-backed `client_id` from a small local state file. If the caller passes an invalid `client_id`, the client falls back to the stored UUID and updates the state file.

Before connecting to WebSocket, the client makes an HTTPS POST to the OTA endpoint with the device and application metadata. The response is parsed into one of three states:

1. `activation required`: log the activation message/code and stop without opening WebSocket
2. `ready`: update the in-memory WebSocket URL and token, then continue with the existing handshake/audio flow
3. `error`: log the service error and stop

The WebSocket behavior remains mostly unchanged after bootstrap succeeds, which keeps the new work isolated to the connection setup path.

## Error Handling

- Invalid or missing UUID: generate/store a valid UUID automatically.
- OTA network failure: log the error and abort startup.
- OTA response without WebSocket data: treat as bootstrap failure and abort startup.
- Activation response: print code plus instructions to bind the device, then exit successfully without retry loops.

## Testing

- Unit test `client_id` persistence and fallback from invalid IDs.
- Unit test OTA response parsing for ready and activation-required responses.
- Unit test that OTA-ready responses update the client WebSocket target from the returned URL.
