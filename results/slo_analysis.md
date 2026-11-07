# Task 7: Service Level Objective (SLO) & Error Budget Analysis

## 1. SLO Definition
- **Objective**: "At least 99.0% of all incoming `POST /parse` requests succeed with HTTP 200 within a 30-second latency window."
- **Target**: **99.0%**
- **Evaluation Window**: One 2-minute load test run (120 seconds, 4 concurrent users).

---

## 2. Error Budget Calculation
- **Total Requests in Window**: 57 requests
- **Permissible Error Budget**:
$$\text{Error Budget} = \text{Total Requests} \times (1.0 - \text{Target}) = 57 \times (1.0 - 0.99) = \mathbf{0.57\text{ requests}}$$

In integer request terms over this 120-second window, zero failed requests are permissible to guarantee meeting the 99% threshold.

---

## 3. Empirical Results & Budget Consumption
- **Successful Requests**: 57
- **Failed Requests**: 0
- **Measured Availability**: **100.0%**
- **Error Budget Used**: **0.00 requests (0.0%)**
- **Error Budget Remaining**: **100.0%**

The service comfortably met the Service Level Objective with 0% budget depletion.
