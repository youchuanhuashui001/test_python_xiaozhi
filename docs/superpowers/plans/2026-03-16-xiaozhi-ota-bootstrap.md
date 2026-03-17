# Xiaozhi OTA Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Xiaozhi OTA bootstrap, persistent `client_id`, and activation-exit handling to the Python client before the existing WebSocket audio flow starts.

**Architecture:** Keep the current `WebSocketClient` as the main runtime object, but move the pre-connection logic into small helpers for identity persistence and OTA response parsing. Only after OTA returns a usable WebSocket URL/token should the client enter the existing handshake and audio loop.

**Tech Stack:** Python 3, `asyncio`, `websockets`, stdlib `unittest`, stdlib `urllib`

---

## Chunk 1: Bootstrap helpers and tests

### Task 1: Add failing tests for identity persistence

**Files:**
- Create: `tests/test_client_bootstrap.py`
- Modify: `client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_invalid_client_id_falls_back_to_persisted_uuid():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: FAIL because bootstrap helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def _load_or_create_client_id(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: PASS for the identity test.

### Task 2: Add failing tests for OTA parsing

**Files:**
- Modify: `tests/test_client_bootstrap.py`
- Modify: `client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_apply_ota_ready_response_updates_websocket_target():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: FAIL because OTA parsing/configuration is missing.

- [ ] **Step 3: Write minimal implementation**

```python
def _apply_bootstrap_response(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: PASS for ready and activation cases.

## Chunk 2: Wire bootstrap into startup flow

### Task 3: Run OTA before WebSocket connect

**Files:**
- Modify: `client.py`
- Test: `tests/test_client_bootstrap.py`

- [ ] **Step 1: Write the failing test**

```python
def test_bootstrap_result_controls_startup_behavior():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: FAIL because startup does not call OTA yet.

- [ ] **Step 3: Write minimal implementation**

```python
async def connect(self):
    if not await self.bootstrap():
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: PASS with bootstrap gating startup.

### Task 4: Document user operations in runtime logs

**Files:**
- Modify: `client.py`

- [ ] **Step 1: Add activation log guidance**

```python
logger.info("请先使用激活码在小智平台绑定设备，然后重新运行客户端。")
```

- [ ] **Step 2: Verify with tests**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: PASS

### Task 5: Final verification

**Files:**
- Modify: `client.py`
- Modify: `tests/test_client_bootstrap.py`

- [ ] **Step 1: Run the focused unit tests**

Run: `python3 -m unittest tests.test_client_bootstrap -v`
Expected: PASS

- [ ] **Step 2: Run a syntax check**

Run: `python3 -m py_compile client.py tests/test_client_bootstrap.py`
Expected: PASS

- [ ] **Step 3: Review the diff**

Run: `git diff -- client.py tests/test_client_bootstrap.py docs/superpowers/specs/2026-03-16-xiaozhi-ota-bootstrap-design.md docs/superpowers/plans/2026-03-16-xiaozhi-ota-bootstrap.md`
Expected: Only OTA/bootstrap, persistent `client_id`, and activation guidance changes.
