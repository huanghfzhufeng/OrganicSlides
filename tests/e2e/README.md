# E2E Tests - Phase 3

## Overview

E2E tests for Phase 3.5 validate the complete workflow from project creation through PPTX generation and download.

## Current Status

**19 E2E test stubs written and passing** ✅

These are **scaffold tests** with mock SSE event data, designed to work once Tasks #13 and #14 are complete:
- Task #13 (frontend-engineer): UI with render path selection
- Task #14 (backend-engineer): API and SSE event implementation

## Test Structure

### Path A Tests (HTML-based rendering)
- `test_full_workflow_path_a` - Complete workflow with Path A
- `test_sse_event_flow_path_a` - Verify event sequence for HTML rendering
- `test_pptx_validity_path_a` - Validate generated PPTX structure

### Path B Tests (Image-based rendering)
- `test_full_workflow_path_b` - Complete workflow with Path B
- `test_image_generation_progress_path_b` - Image generation progress events
- `test_pptx_with_images_path_b` - PPTX with generated images

### Auto/Mixed Rendering Tests
- `test_full_workflow_auto_mixed` - Auto mode with mixed paths
- `test_mixed_path_selection` - Verify Path A and B selection logic

### Error Scenario Tests
- `test_invalid_style_id` - Invalid style handling
- `test_empty_prompt_validation` - Empty prompt rejection
- `test_missing_api_key_error` - Missing API key handling
- `test_network_timeout_error` - Timeout error handling

### SSE Event Structure Tests
- `test_status_event_format` - Verify status event structure
- `test_render_progress_event_format` - Verify progress event structure
- `test_complete_event_format` - Verify completion event structure
- `test_error_event_format` - Verify error event structure

### Download & Validation Tests
- `test_pptx_file_download` - File availability for download
- `test_pptx_file_validity` - PPTX can be opened
- `test_pptx_file_not_empty` - File size validation

## Mock Data

The tests use mock SSE event generators that simulate:

```
Status Events:
- planning
- researching
- writing
- rendering

HITL Events:
- waiting_for_approval with outline

Render Progress Events:
- rendering/generating_image/complete/failed
- Per-slide tracking
- Optional thumbnail URLs

Completion Events:
- Final PPTX path

Error Events:
- error_type, message, details
```

## Finalization Steps

When Task #13 and #14 are complete:

1. **Replace mock SSE generators** with actual HTTP client calls:
   ```python
   @patch("httpx.AsyncClient.stream")
   def test_...(self, mock_stream):
       # Use real API client instead of mock_sse_events_path_a()
   ```

2. **Add real style IDs** from the database:
   ```python
   style = db.query(StyleJSON).first()
   project_data["style"] = style.id
   ```

3. **Test with real UI components**:
   - Verify render path selection UI
   - Verify progress cards rendering
   - Verify download button functionality

4. **Add integration with browser/client**:
   - SSE reconnection on disconnect
   - Real file download handling
   - UI state synchronization

## Dependencies

- Task #13 (Phase 3.1): Frontend UI with render path selection
- Task #14 (Phase 3.2): Backend API with SSE events and render_path_preference
- Task #8 (Phase 2.2): Rendering pipeline (already complete)

## Running Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test class
pytest tests/e2e/test_full_workflow.py::TestFullWorkflowPathA -v

# Run with verbose output
pytest tests/e2e/ -vv -s
```

## Notes

- All tests use mock data and don't require running services
- Tests are isolated and can run in any order
- Uses temporary directories for PPTX file generation
- Mock events follow the expected SSE format specification
- Ready to be converted to integration tests with real client once API is ready
