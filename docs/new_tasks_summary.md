# Literature-Based Multi-Turn Network Tasks - Summary (FRR-Compatible)

## Overview
Five multi-turn benchmark tasks created based on credible literature, industry certifications, and real-world case studies. **All tasks are compatible with FRR (Free Range Routing) platform** which is lightweight and freely available in Containerlab.

---

## Task 1: Basic Level - RIP Routing Configuration
**File**: `ccna_rip_routing_basic.json`  
**Complexity**: Basic (CCNA-level)  
**Expected Time**: 20 minutes  
**Expected Turns**: 25-40  
**Platform**: FRR ✅

**Description**: Basic RIPv2 configuration across 4 routers in a small enterprise network. Configure RIP with network statements, enable RIPv2, and verify full routing table convergence.

**Literature Basis**:
- CCNA 200-301 curriculum (RIP as foundational distance-vector protocol)
- Cisco CCNA official cert guide
- RFC 2453 (RIPv2 specification)

**Time Justification**:
- CCNA RIP labs: 15-25 minutes for basic configs (CCNA tutorials, 9tut.com)
- Research shows RIP "can be deployed in a matter of minutes" (freeccnaworkbook.com)
- 20 minutes represents realistic time for 4-router RIPv2 configuration

**Citation**: "CCNA 200-301 curriculum covers RIP as foundational distance-vector protocol. RIP configuration simpler than OSPF: 15-25min for basic configs. Research confirms RIP deployment takes 15-45 minutes depending on complexity (linuxtiwary.com, networklessons.com)."

**FRR Compatibility**: FRR fully supports RIPv1/v2 (RFC 2453 compliant). Commands similar to Cisco IOS.

---

## Task 2: Intermediate Level - Multi-Area OSPF
**File**: `ccnp_multiarea_ospf_intermediate.json`  
**Complexity**: Intermediate (CCNP-level)  
**Expected Time**: 50 minutes  
**Expected Turns**: 50-70  
**Platform**: FRR ✅

**Description**: Multi-area OSPF deployment across 5 routers with Area 0 (backbone), Area 1, and Area 2. Configure OSPF with proper area assignments, route summarization at ABRs, and verify full convergence.

**Literature Basis**:
- CCNP ENARSI curriculum (exam 300-410)
- RFC 2328 (OSPF v2)
- Cisco CCNP official cert guide

**Time Justification**:
- CCNP multi-area OSPF: 30-90 minutes
- ExamCollection practice: 40-60 minute target
- 50 minutes is mid-range for intermediate OSPF tasks

**Citation**: "CCNP ENARSI training materials. Multi-area OSPF configuration time: 30-90 minutes. ExamCollection CCNP practice: 40-60min target."

**FRR Compatibility**: FRR fully supports OSPFv2 (RFC 2328). Multi-area configuration, ABRs, route summarization all supported.

---

## Task 3: Expert Level - Dual-Homed BGP with Traffic Engineering
**File**: `ccie_bgp_dual_homing_expert.json`  
**Complexity**: Expert (CCIE-level)  
**Expected Time**: 120 minutes  
**Expected Turns**: 100-140  
**Platform**: FRR ✅

**Description**: Enterprise dual-homed BGP with redundant ISP connections. Configure eBGP peering with two ISPs, implement route filtering with prefix-lists and route-maps, configure local-preference, implement AS-PATH prepending, and optimize convergence times.

**Literature Basis**:
- CCIE Service Provider and Enterprise lab scenarios
- RFC 4271 (BGP-4)
- Cisco CCIE official cert guide
- ISP multi-homing best practices

**Time Justification**:
- CCIE lab: 8+ hours total (this represents 1 major scenario)
- BGP convergence optimization research (Noction)
- Complex BGP deployments: hours to days (Catchpoint)
- 120 minutes for one complete BGP scenario

**Citation**: "CCIE lab exam format (8+ hours total). BGP convergence optimization: default 180s can be reduced to 30s (Noction). Complex BGP deployments: hours to days (Catchpoint)."

**FRR Compatibility**: FRR has full BGP support (RFC 4271). Prefix-lists, route-maps, local-preference, AS-PATH prepending, timers - all supported.

---

## Task 4: Issue-Specific - OSPF Adjacency Troubleshooting
**File**: `troubleshoot_ospf_adjacency_issue.json`  
**Complexity**: Intermediate  
**Expected Time**: 35 minutes  
**Expected Turns**: 25-45  
**Platform**: FRR ✅

**Description**: OSPF adjacency troubleshooting scenario. A 4-router OSPF network has area ID mismatch preventing full adjacency formation. Identify root cause and restore full OSPF neighbor relationships.

**Literature Basis**:
- CCNP TSHOOT curriculum
- RFC 2328 (OSPF v2) - adjacency requirements
- CBT Nuggets CCNP troubleshooting course
- Network engineering case studies

**Time Justification**:
- ExamCollection CCNP: "Fix OSPF issue within 10 minutes" (expert)
- Industry MTTR for configuration errors: 15min-4hr (IoRiver)
- Routing problems: 30min-8hr (Network Defense Blog)
- 35 minutes = realistic troubleshooting time (average)

**Citation**: "ExamCollection CCNP practice: 'Fix OSPF issue within 10 minutes'. Industry MTTR for configuration errors: 15min-4hr (IoRiver). OSPF adjacency problems: 30min-8hr resolution time."

**FRR Compatibility**: FRR OSPF troubleshooting uses standard commands: `show ip ospf neighbor`, `show ip ospf interface`. Area mismatch scenario fully reproducible.

---

## Task 5: Issue-Specific - BGP Route Filtering Troubleshooting
**File**: `troubleshoot_bgp_route_filtering.json`  
**Complexity**: Intermediate  
**Expected Time**: 40 minutes  
**Expected Turns**: 30-50  
**Platform**: FRR ✅

**Description**: BGP route filtering troubleshooting. Enterprise edge router advertising all internal routes to ISP instead of only approved public prefixes. Diagnose missing route-map application and fix filtering.

**Literature Basis**:
- CCNP ENARSI and CCIE curricula
- RFC 4271 (BGP-4)
- Cisco BGP best practices
- Real-world route leak incidents

**Time Justification**:
- BGP policy issues: 30min to hours (Catchpoint)
- Configuration errors MTTR: 15min-4hr
- Fast diagnosis (expert): 15-25min
- Average resolution: 30-60min
- 40 minutes includes diagnosis, fix, soft-reset, verification

**Citation**: "CCNP ENARSI and CCIE curricula. Industry MTTR for configuration errors: 15min-4hr. BGP issues range from 30 minutes (simple) to hours (complex policy) based on Catchpoint BGP analysis."

**FRR Compatibility**: FRR BGP filtering fully supported: prefix-lists, route-maps, neighbor route-map application, soft reset. Same workflow as Cisco IOS.

---

## Summary Statistics

| Task | Complexity | Time (min) | Turns | FRR Compatible | Basis |
|------|------------|------------|-------|----------------|-------|
| RIP Routing | Basic | 20 | 25-40 | ✅ | CCNA curriculum |
| Multi-Area OSPF | Intermediate | 50 | 50-70 | ✅ | CCNP ENARSI |
| Dual-Homed BGP | Expert | 120 | 100-140 | ✅ | CCIE lab scenarios |
| OSPF Troubleshooting | Intermediate | 35 | 25-45 | ✅ | CCNP TSHOOT + MTTR |
| BGP Troubleshooting | Intermediate | 40 | 30-50 | ✅ | CCNP/CCIE + MTTR |

**Total Expected Time**: 265 minutes (4.4 hours) for all five tasks

---

## FRR Platform Compatibility Notes

**Why FRR?**
- Free and open-source routing software suite
- Lightweight (works well in Containerlab)
- RFC-compliant implementations (RIP, OSPF, BGP)
- Similar command syntax to Cisco IOS (easier for agent learning)

**Supported Protocols**:
- ✅ **RIP**: RIPv1/v2 (RFC 2453)
- ✅ **OSPF**: OSPFv2 (RFC 2328), multi-area, ABRs, summarization
- ✅ **BGP**: BGP-4 (RFC 4271), eBGP, iBGP, route-maps, prefix-lists, AS-PATH manipulation
- ✅ **Static Routing**: Full support

**NOT Supported in FRR**:
- ❌ **VLANs**: FRR is a routing daemon, not a switch
- ❌ **Layer 2 switching**: No switchport commands
- ⚠️ **VLAN sub-interfaces**: Can be configured via Linux `ip` commands on Alpine, but this is not CCNA curriculum

---

## Key Research Sources Referenced

1. **Certifications**: CCNA (200-301), CCNP ENARSI (300-410), CCNP TSHOOT, CCIE R&S/SP
2. **RFCs**: RFC 2328 (OSPF v2), RFC 2453 (RIPv2), RFC 4271 (BGP-4)
3. **Training**: Orhan Ergun CCNP, Flackbox, CBT Nuggets, ExamCollection, 9tut.com
4. **Industry Data**: IoRiver Network Downtime Study, Catchpoint BGP analysis, Network Defense Blog
5. **Community**: Reddit CCNA/CCNP, networklessons.com, freeccnaworkbook.com
6. **Vendors**: Cisco official cert guides, Noction BGP optimization, FRRouting.org documentation

---

## Design Principles

1. **Platform Compatibility**: All tasks verified to work with FRR/Containerlab
2. **Time Estimates from Literature**: CCNA sims (5-10min), CCNP labs (10-60min), CCIE scenarios (1-3hr), MTTR data (15min-4hr)
3. **Topologies from Curricula**: RIP (CCNA), multi-area OSPF (CCNP), dual-homed BGP (CCIE), troubleshooting (CCNP TSHOOT, real-world MTTR)
4. **RealComplexity Progression**: Basic (CCNA) → Intermediate (CCNP) → Expert (CCIE)
5. **Proper Citations**: Every task includes research_context with citation, literature_basis, time_justification, and platform_notes

---

## Changes from Original Design

**Replaced**: CCNA VLAN Campus task  
**Reason**: FRR does not support VLAN configuration (it's a routing daemon, not a switch)  
**New Task**: CCNA RIP Routing (still basic-level, still literature-grounded, FRR-compatible)

All other tasks (OSPF, BGP) were already FRR-compatible and required no changes.
