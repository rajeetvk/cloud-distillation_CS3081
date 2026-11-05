# Subnet Allocation Plan

Address Block: `10.20.0.0/16`

## 1. Subnet Requirements and Sizing

The subnets are allocated in descending order of requirement size, starting strictly at `10.20.0.0`. Each subnet is placed contiguously right after the previous subnet using the smallest CIDR prefix that accommodates the required number of usable hosts.

Formula for usable hosts:
$$\text{Usable Hosts} = 2^{32 - \text{prefix}} - 2$$

### Requirement Breakdown

1. **`app` subnet**:
   - Hosts needed: 1,000
   - Smallest power of 2: $2^{10} = 1024 \ge 1000 + 2 = 1002$
   - Host bits: 10
   - Prefix length: $32 - 10 = /22$
   - Usable hosts: $2^{10} - 2 = 1,022$
   - Starting Address: `10.20.0.0`
   - Subnet Mask: `255.255.252.0`
   - Address Range: `10.20.0.0` - `10.20.3.255`
   - Usable Host Range: `10.20.0.1` - `10.20.3.254`
   - Broadcast Address: `10.20.3.255`

2. **`public` subnet**:
   - Hosts needed: 250
   - Smallest power of 2: $2^8 = 256 \ge 250 + 2 = 252$
   - Host bits: 8
   - Prefix length: $32 - 8 = /24$
   - Usable hosts: $2^8 - 2 = 254$
   - Starting Address (immediately after `10.20.3.255`): `10.20.4.0`
   - Subnet Mask: `255.255.255.0`
   - Address Range: `10.20.4.0` - `10.20.4.255`
   - Usable Host Range: `10.20.4.1` - `10.20.4.254`
   - Broadcast Address: `10.20.4.255`

3. **`data` subnet**:
   - Hosts needed: 100
   - Smallest power of 2: $2^7 = 128 \ge 100 + 2 = 102$
   - Host bits: 7
   - Prefix length: $32 - 7 = /25$
   - Usable hosts: $2^7 - 2 = 126$
   - Starting Address (immediately after `10.20.4.255`): `10.20.5.0`
   - Subnet Mask: `255.255.255.128`
   - Address Range: `10.20.5.0` - `10.20.5.127`
   - Usable Host Range: `10.20.5.1` - `10.20.5.126`
   - Broadcast Address: `10.20.5.127`

4. **`management` subnet**:
   - Hosts needed: 20
   - Smallest power of 2: $2^5 = 32 \ge 20 + 2 = 22$
   - Host bits: 5
   - Prefix length: $32 - 5 = /27$
   - Usable hosts: $2^5 - 2 = 30$
   - Starting Address (immediately after `10.20.5.127`): `10.20.5.128`
   - Subnet Mask: `255.255.255.224`
   - Address Range: `10.20.5.128` - `10.20.5.159`
   - Usable Host Range: `10.20.5.129` - `10.20.5.158`
   - Broadcast Address: `10.20.5.159`

---

## 2. Summary Table

| Subnet | Network Address | Prefix Length | Usable Host Range | Broadcast Address | Usable Hosts |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **app** | `10.20.0.0` | `/22` | `10.20.0.1` - `10.20.3.254` | `10.20.3.255` | 1022 |
| **public** | `10.20.4.0` | `/24` | `10.20.4.1` - `10.20.4.254` | `10.20.4.255` | 254 |
| **data** | `10.20.5.0` | `/25` | `10.20.5.1` - `10.20.5.126` | `10.20.5.127` | 126 |
| **management** | `10.20.5.128` | `/27` | `10.20.5.129` - `10.20.5.158` | `10.20.5.159` | 30 |

---

## 3. Explanations (NACL Architecture)

### Why a Stateless NACL Needs Separate Rules for Reply Traffic
Unlike stateful firewalls (or Security Groups) that track connection state in a connection-tracking table (returning SYN-ACK or ACK packets automatically as part of an established flow), a Network Access Control List (NACL) is completely **stateless**. Every single packet is evaluated in isolation against the rule set without any knowledge of prior handshakes or sessions. 

When a client initiates an inbound TCP connection to web ports 80/443 on the load balancer, the load balancer must send response packets back to the client. The client's destination port for that reply is an ephemeral port (ports 1024–65535). Because the NACL does not remember that this outbound packet is part of an approved inbound request, an explicit **outbound rule** permitting traffic to client ephemeral ports (`0.0.0.0/0`, ports 1024–65535) is mandatory. Similarly, when the load balancer initiates connections to the backend application servers on TCP port 8000, the response packets returning from the application servers target the load balancer's ephemeral ports; thus, an explicit **inbound rule** permitting ephemeral port traffic from the `app` subnet (`10.20.0.0/22`) is required.

### Why Rule Order Matters for the `198.51.100.0/24` Block
NACL evaluation follows a strict **first-match** semantic: rules are evaluated in ascending numerical order (from lowest rule number to highest rule number), and the first rule whose criteria match the packet immediately decides its disposition (`allow` or `deny`), terminating further evaluation.

If the rule blocking the abusive subnet `198.51.100.0/24` were placed after the generic web allow rule (e.g., rule 200 DENY `198.51.100.0/24` vs rule 100 ALLOW `0.0.0.0/0` on port 443), an incoming HTTPS packet from `198.51.100.9` would match rule 100 first and be allowed through. The deny rule would never be reached or evaluated. Therefore, the specific **DENY** rule for `198.51.100.0/24` must have a lower rule number (e.g., rule 100) than the general **ALLOW** rules (rules 110, 120) to guarantee that malicious traffic is dropped before broader access grants are processed.
