import time

class Stopwatch:
    def __init__(self):
        self.start_time = None
        self.elapsed_time = 0

    def start(self):
        if self.start_time is not None:
            raise RuntimeError("Stopwatch is already running")
        self.start_time = time.perf_counter() * 1000

    def stop(self):
        if self.start_time is None:
            raise RuntimeError("Stopwatch is not running")
        end_time = time.perf_counter() * 1000
        self.elapsed_time += end_time - self.start_time
        self.start_time = None

    def reset(self):
        self.start_time = None
        self.elapsed_time = 0

    def elapsed(self) -> float:
        if self.start_time is not None:
            return self.elapsed_time + (time.perf_counter() * 1000 - self.start_time)
        return self.elapsed_time

# 示例用法
stopwatch = Stopwatch()
stopwatch.start()
time.sleep(1)  # 模拟耗时操作
stopwatch.stop()
print(f"Elapsed time: {stopwatch.elapsed()} seconds")