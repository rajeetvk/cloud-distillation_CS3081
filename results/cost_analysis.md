# Task 7: Infrastructure Cost Estimation Analysis

Using the hypothetical rates defined in `data/rate_card.json`, this document details the step-by-step arithmetic to estimate the cost of serving 1,000 requests on our Kubernetes cluster deployment.

---

## 1. Rate Card Pricing
- **vCPU per hour**: ₹3.50 INR
- **GiB Memory per hour**: ₹0.45 INR
- **Billing Policy**: Replicas are billed continuously for their resource limits (CPU and memory) for every hour they run, regardless of idle or active time.

---

## 2. Resource Allocation per Replica
From `cluster/app.yaml`:
- **CPU limit**: `1000m` = `1.0 vCPU`
- **Memory limit**: `1Gi` = `1.0 GiB`
- **Running Replicas**: `2` (steady-state production deployment)

$$\text{Hourly Cost per Replica} = (1.0 \times ₹3.50) + (1.0 \times ₹0.45) = ₹3.95\text{ INR/hr}$$
$$\text{Hourly Cost for all 2 Replicas} = 2 \times ₹3.95 = ₹7.90\text{ INR/hr}$$

---

## 3. Throughput & Request Volume
From our 2-minute Locust stress test (`results/loadtest_stats.csv`):
- **Test Duration**: 120 seconds (2.0 minutes)
- **Successful Requests Served**: 57 requests
- **Extrapolated Hourly Throughput**:
$$\text{Requests per Hour} = \frac{57\text{ requests}}{2\text{ minutes}} \times 60\text{ minutes} = 1,710\text{ requests/hour}$$

---

## 4. Cost per 1,000 Requests Calculation
Following the mandatory formula:
$$\text{Cost per 1,000 Requests} = \left(\frac{\text{Hourly Cost of all Running Replicas}}{\text{Requests Served per Hour}}\right) \times 1,000$$

$$\text{Cost per 1,000 Requests} = \left(\frac{₹7.90}{1,710}\right) \times 1,000 = ₹4.61988 \approx \mathbf{₹4.62\text{ INR}}$$

*(Under peak continuous sequential load of ~1,222 requests/hour, cost is ₹6.46 INR per 1,000 requests).*
