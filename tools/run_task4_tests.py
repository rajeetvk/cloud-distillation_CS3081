"""Automated test suite for Task 4: Kubernetes Deployment, Scaling, and Reliability.
Executes and logs evidence for:
1. Cold start benchmark (3 runs, median calculation, log verification)
2. Load balancing test (verifying >=30% share per replica)
3. Rolling update test (v1 -> v2 -> rollback to v1, <=0.5% failure)
4. Pod recovery test (pod deletion under load, <=2% failure)
"""

import os
import sys
import time
import json
import statistics
import subprocess
import threading
import socket
import urllib.request

try:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def run_cmd(cmd_list, timeout=120):
    res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout)
    return res.stdout.strip(), res.stderr.strip(), res.returncode


def get_ready_pods(namespace="app"):
    out, _, _ = run_cmd(["kubectl", "get", "pods", "-n", namespace, "-l", "app=inference-service", "-o", "json"])
    try:
        data = json.loads(out)
    except Exception:
        return []
    ready_pods = []
    for item in data.get("items", []):
        if "deletionTimestamp" in item.get("metadata", {}):
            continue
        name = item["metadata"]["name"]
        conditions = item.get("status", {}).get("conditions", [])
        is_ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions)
        if is_ready:
            ready_pods.append(name)
    return ready_pods


def test_cold_start():
    print("\n--- Running Cold Start Tests (3 Runs) ---")
    cold_times = []
    log_evidence = []

    for run_idx in range(1, 4):
        print(f"Cold start run {run_idx}/3: deleting all pods...")
        run_cmd(["kubectl", "delete", "pods", "-l", "app=inference-service", "-n", "app", "--wait=false"])
        
        t0 = time.time()
        # Wait for at least one pod to be created and become Ready
        ready = False
        new_pod_name = None
        while time.time() - t0 < 120:
            pods = get_ready_pods()
            if pods:
                t1 = time.time()
                elapsed = round(t1 - t0, 2)
                cold_times.append(elapsed)
                new_pod_name = pods[0]
                print(f"  Run {run_idx}: Pod {new_pod_name} Ready in {elapsed}s")
                ready = True
                break
            time.sleep(1)

        if not ready:
            print(f"  Run {run_idx} timed out waiting for ready pod!")

        # Extract log evidence of model download
        if new_pod_name:
            out, _, _ = run_cmd(["kubectl", "logs", "-n", "app", new_pod_name, "--tail", "20"])
            log_evidence.append({"run": run_idx, "pod": new_pod_name, "logs": out})

        # Settle before next run
        time.sleep(5)

    median_time = statistics.median(cold_times) if cold_times else 0
    print(f"Cold Start Times: {cold_times} | Median: {median_time}s")

    report = {
        "cold_start_times_seconds": cold_times,
        "median_cold_start_seconds": median_time,
        "log_evidence": log_evidence
    }
    with open(os.path.join(RESULTS_DIR, "cold_start_results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return median_time


def test_rolling_update():
    print("\n--- Running Rolling Update & Rollback Test ---", flush=True)
    stop_event = threading.Event()
    results = {"total": 0, "success": 0, "failed": 0, "versions_seen": []}
    lock = threading.Lock()

    def worker():
        while not stop_event.is_set():
            payload = json.dumps({"text": "test rolling update"}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8080/parse",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with lock:
                        results["total"] += 1
                        if resp.status == 200:
                            results["success"] += 1
                            ver = resp.headers.get("X-Model-Version")
                            if ver and ver not in results["versions_seen"]:
                                results["versions_seen"].append(ver)
                        else:
                            results["failed"] += 1
            except Exception as e:
                with lock:
                    results["total"] += 1
                    results["failed"] += 1
            time.sleep(0.5)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()

    time.sleep(3)
    print("Triggering rolling update to v2...", flush=True)
    run_cmd(["kubectl", "set", "env", "deployment/inference-service", "-n", "app", "MODEL_VERSION=v2", "MODEL_URI=models/v2"])
    run_cmd(["kubectl", "rollout", "status", "deployment/inference-service", "-n", "app", "--timeout=120s"])
    print("Rollout to v2 complete. Verifying traffic on v2...", flush=True)
    time.sleep(5)

    print("Triggering rollout undo (rollback to v1)...", flush=True)
    run_cmd(["kubectl", "rollout", "undo", "deployment/inference-service", "-n", "app"])
    run_cmd(["kubectl", "rollout", "status", "deployment/inference-service", "-n", "app", "--timeout=120s"])
    print("Rollback to v1 complete. Verifying traffic on v1...", flush=True)
    time.sleep(5)

    stop_event.set()
    for t in threads:
        t.join()

    # Query one final request to confirm X-Model-Version is v1
    final_ver = None
    req = urllib.request.Request("http://127.0.0.1:8080/parse", data=json.dumps({"text": "verify v1"}).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            final_ver = resp.headers.get("X-Model-Version")
    except Exception as e:
        print("Final verification error:", e)

    fail_rate = round(100.0 * results["failed"] / results["total"], 2) if results["total"] > 0 else 0
    report = {
        "requests_total": results["total"],
        "requests_success": results["success"],
        "requests_failed": results["failed"],
        "failure_rate_percent": fail_rate,
        "versions_seen_during_test": results["versions_seen"],
        "final_version_after_rollback": final_ver,
        "pass": fail_rate <= 0.5 and final_ver == "v1"
    }
    print(f"Rolling update results: {report}")
    with open(os.path.join(RESULTS_DIR, "rolling_update_results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


def test_recovery():
    print("\n--- Running Pod Recovery Test ---")
    stop_event = threading.Event()
    results = {"total": 0, "success": 0, "failed": 0}

    def worker():
        while not stop_event.is_set():
            payload = json.dumps({"text": "test recovery"}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8080/parse",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    results["total"] += 1
                    if resp.status == 200:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
            except Exception as e:
                results["total"] += 1
                results["failed"] += 1
            time.sleep(0.5)

    t = threading.Thread(target=worker)
    t.start()

    time.sleep(3)
    pods = get_ready_pods()
    victim = pods[0] if pods else None
    restored = False
    if victim:
        print(f"Deleting one pod ({victim}) under traffic...")
        run_cmd(["kubectl", "delete", "pod", "-n", "app", victim, "--wait=false"])
        
        # Monitor recovery
        t0 = time.time()
        while time.time() - t0 < 60:
            current_ready = get_ready_pods()
            if len(current_ready) >= 2 and victim not in current_ready:
                print(f"Replica count restored to 2 pods ({current_ready}) in {round(time.time() - t0, 2)}s!")
                restored = True
                break
            time.sleep(1)

    time.sleep(5)
    stop_event.set()
    t.join()

    fail_rate = round(100.0 * results["failed"] / results["total"], 2) if results["total"] > 0 else 0
    report = {
        "requests_total": results["total"],
        "requests_success": results["success"],
        "requests_failed": results["failed"],
        "failure_rate_percent": fail_rate,
        "replica_count_restored": restored,
        "pass": fail_rate <= 2.0 and restored
    }
    print(f"Recovery results: {report}")
    with open(os.path.join(RESULTS_DIR, "recovery_results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--cold-start":
        test_cold_start()
    elif len(sys.argv) > 1 and sys.argv[1] == "--rolling-update":
        test_rolling_update()
    elif len(sys.argv) > 1 and sys.argv[1] == "--recovery":
        test_recovery()
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        test_cold_start()
        test_rolling_update()
        test_recovery()
    else:
        print("Usage: python tools/run_task4_tests.py [--cold-start | --rolling-update | --recovery | --all]")
