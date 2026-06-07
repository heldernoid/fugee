"""tests/unit/test_loop_isolation.py — per-session loop isolation (T019).

Each Gradio session gets its own AgentLoop via the factory; their steering
queues and abort flags must be independent (no shared mutable state).
"""

from agent.loop import AgentLoop, create_loop


def test_factory_returns_distinct_instances():
    a = create_loop()
    b = create_loop()
    assert isinstance(a, AgentLoop) and isinstance(b, AgentLoop)
    assert a is not b


def test_steering_queue_is_per_instance():
    a = create_loop()
    b = create_loop()
    a.steer("a-message")
    assert a.steering_queue.qsize() == 1
    assert b.steering_queue.qsize() == 0


def test_abort_flag_is_per_instance():
    a = create_loop()
    b = create_loop()
    a.abort()
    assert a.abort_event.is_set()
    assert not b.abort_event.is_set()


def test_reset_clears_abort_and_steering():
    a = create_loop()
    a.steer("x")
    a.abort()
    a.reset()
    assert not a.abort_event.is_set()
    assert a.steering_queue.empty()
