from backend.jobs.job_queue import JobQueue


def test_add_and_get_job():

    queue = JobQueue()

    assert queue.add("JOB-001") is True
    assert queue.size() == 1

    job_id = queue.get(timeout=1)

    assert job_id == "JOB-001"
    assert queue.size() == 0


def test_duplicate_job_is_not_added():

    queue = JobQueue()

    assert queue.add("JOB-001") is True
    assert queue.add("JOB-001") is False

    assert queue.size() == 1


def test_empty_queue_returns_none():

    queue = JobQueue()

    job_id = queue.get(timeout=0.1)

    assert job_id is None


def test_task_done():

    queue = JobQueue()

    queue.add("JOB-001")

    job_id = queue.get(timeout=1)

    assert job_id == "JOB-001"

    queue.task_done()

    queue.wait_until_empty()


def test_is_queued():

    queue = JobQueue()

    assert queue.is_queued("JOB-001") is False

    queue.add("JOB-001")

    assert queue.is_queued("JOB-001") is True

    job_id = queue.get(timeout=1)

    assert job_id == "JOB-001"

    assert queue.is_queued("JOB-001") is False

    queue.task_done()