# Acme Retail Shipping Procedures
**Version 5.3 | Effective Date: March 1, 2025**
*For Internal Use — Fulfillment Center Staff, Store Operations, and E-Commerce Teams*

---

## Overview

This document covers Acme Retail's end-to-end shipping procedures for all order channels, including standard e-commerce orders, same-day delivery, ship-from-store, and B2B/wholesale shipments. All staff involved in the pick, pack, ship, and returns logistics chain should be familiar with the relevant sections of this guide.

Questions should be directed to your Fulfillment Supervisor or the Logistics Operations team at **logistics@acmeretail.com / x5100**.

---

## Table of Contents

1. Shipping Channels & Order Types
2. Carrier Partners
3. Domestic Shipping Options & SLAs
4. International Shipping
5. Fulfillment Center Operations
6. Ship-From-Store (SFS) Procedures
7. Same-Day & Express Delivery
8. Packaging Standards
9. Labeling Requirements
10. Hazardous & Restricted Materials
11. Order Tracking & Customer Communication
12. Lost, Delayed, or Damaged Shipments
13. Return Logistics
14. B2B & Wholesale Shipments
15. Peak Season Protocols
16. Carrier Cutoff Times

---

## 1. Shipping Channels & Order Types

Acme Retail ships orders through the following channels:

| Order Type | Origin | System |
|---|---|---|
| **Standard E-Commerce** | Fulfillment Center (FC) | OMS → WMS → Carrier |
| **Ship-From-Store (SFS)** | Retail store | OMS → StoreOps App → Carrier |
| **Same-Day Delivery** | Local store or FC | OMS → Dispatch Platform → Courier |
| **Buy Online, Pick Up In-Store (BOPIS)** | Retail store | OMS → Store Fulfillment Queue |
| **Curbside Pickup** | Retail store | OMS → Curbside App |
| **B2B / Wholesale** | FC or direct vendor | EDI / Manual PO → Freight Carrier |
| **Marketplace Orders** | FC or SFS | Marketplace API → WMS |

All orders flow through the **Acme Order Management System (OMS)**, accessible at **oms.acmeretail.internal**. Associates should never attempt to fulfill or modify orders outside of the OMS workflow.

---

## 2. Carrier Partners

Acme Retail maintains preferred carrier relationships negotiated by the Logistics team. Do not arrange shipments with unapproved carriers without prior authorization.

| Carrier | Services Used | Account Code |
|---|---|---|
| **UPS** | Ground, 2-Day Air, Next Day Air, Returns | ARC-UPS-88421 |
| **FedEx** | Ground, Express, Freight (large items) | ARC-FDX-30917 |
| **USPS** | First-Class, Priority Mail (small parcels, rural) | ARC-USPS-7741 |
| **OnTrac** | Regional ground (Western U.S. only) | ARC-OTR-5502 |
| **DHL** | International shipments | ARC-DHL-INT-209 |
| **Roadie / GoShip** | Same-day local delivery | Dispatched via platform |
| **XPO Logistics** | LTL Freight (furniture, large items) | ARC-XPO-FR-104 |
| **Acme Private Fleet** | B2B bulk deliveries within 150-mile radius of FCs | Internal dispatch |

All carrier labels must be generated through the **AcmeShip** label printing system. Do not use carrier websites directly to generate labels, as this bypasses negotiated rates and tracking integration.

---

## 3. Domestic Shipping Options & SLAs

### 3.1 Standard Customer-Facing Shipping Options

| Service | Carrier | Estimated Transit Time | Cost to Customer |
|---|---|---|---|
| Standard Shipping | UPS Ground / USPS Priority | 5–7 business days | $5.99 (free over $35) |
| Expedited Shipping | UPS 2-Day Air | 2 business days | $12.99 |
| Overnight Shipping | UPS Next Day Air | 1 business day | $24.99 |
| Same-Day Delivery | Roadie / GoShip | Within 4 hours (select zip codes) | $14.99 |
| Free Standard Shipping | UPS Ground / USPS | 5–7 business days | Free (orders $35+) |

### 3.2 Internal SLAs (Fulfillment Center to Ship)

| Order Type | SLA |
|---|---|
| Standard orders (in-stock) | Pick, pack, and ship within 1 business day of order |
| Expedited / Overnight orders | Same-day ship if ordered by carrier cutoff |
| Same-day delivery | Ready for courier pickup within 90 minutes of order |
| Pre-orders / backordered items | Ship within 1 business day of inventory receipt |
| Large/freight items | Hand-off to freight carrier within 2 business days |

Orders not shipped within SLA must be flagged in the OMS for supervisor review. Customers with SLA breaches of more than 24 hours are automatically notified and may be eligible for a shipping credit.

---

## 4. International Shipping

Acme Retail ships internationally to **Canada, the United Kingdom, Australia, and Germany** as of March 2025. All other international orders should be declined at checkout.

| Region | Carrier | Transit Time | Duties & Taxes |
|---|---|---|---|
| Canada | DHL Express / Canada Post | 5–10 business days | Collected at checkout (DDP) |
| United Kingdom | DHL Express | 7–12 business days | Collected at checkout (DDP) |
| Australia | DHL Express | 10–15 business days | Customer responsible (DAP) |
| Germany | DHL Express | 7–12 business days | Collected at checkout (DDP) |

**DDP (Delivered Duty Paid):** Duties and taxes are calculated and collected at checkout. No surprise charges for the customer at delivery.
**DAP (Delivered at Place):** Customer is responsible for paying duties and taxes upon delivery. Currently applies to Australia only.

International shipments require a commercial invoice generated automatically by OMS. Associates must not modify international customs documentation.

**Prohibited Items for International Shipment:**
- Electronics with lithium batteries (certain restrictions apply — verify per SKU)
- Aerosols and flammable liquids
- Food and perishables
- Items restricted by destination country laws (verify via the Compliance Lookup Tool in OMS)

---

## 5. Fulfillment Center Operations

Acme Retail operates six fulfillment centers (FCs) across North America:

| FC Code | Location | Sq. Footage | Specialization |
|---|---|---|---|
| FC-CHI | Joliet, IL | 1.2M sq ft | General merchandise, apparel |
| FC-ATL | Covington, GA | 950K sq ft | General merchandise, electronics |
| FC-DAL | Fort Worth, TX | 850K sq ft | General merchandise, furniture |
| FC-LAX | Rialto, CA | 1.1M sq ft | General merchandise, West Coast distribution |
| FC-NJY | Edison, NJ | 780K sq ft | General merchandise, East Coast distribution |
| FC-TOR | Brampton, ON (Canada) | 620K sq ft | Canadian orders, Canadian compliance |

### 5.1 Inbound Receiving

- All vendor inbound shipments must be pre-announced via the **Vendor Portal** at least 48 hours in advance.
- Receiving dock assignments are managed by the FC Dock Scheduler — unannounced deliveries will be refused.
- All inbound inventory is scanned into the WMS at the point of receipt. Discrepancies between PO quantity and received quantity must be documented within 4 hours using the Receiving Discrepancy form.

### 5.2 Inventory Picking

Acme FCs use a combination of zone picking, batch picking, and robotic assist (FC-CHI and FC-LAX only). Pickers follow the WMS-generated pick path displayed on their handheld scanner. Associates should never deviate from the system-assigned pick path without supervisor approval, as this affects wave efficiency metrics.

**Pick accuracy standard:** 99.7% or higher. Associates falling below 99.0% for more than 3 consecutive weeks will be enrolled in a performance improvement plan.

### 5.3 Packing

- Packing stations are assigned by the WMS based on item size and shipping method.
- Associates must use the correct box or poly mailer as directed by the packing screen — do not substitute without supervisor approval.
- All packed items must be weighed and dimensioned at the station; variance between system weight and actual weight of more than 0.5 lbs will trigger a recheck alert.

### 5.4 Quality Control

A random sample of 2% of all outbound orders undergoes a QC check before shipping. QC associates verify item, quantity, packaging integrity, and label accuracy. Items failing QC are returned to the packing station for correction.

---

## 6. Ship-From-Store (SFS) Procedures

Ship-From-Store allows designated retail stores to fulfill online orders directly from store inventory, reducing transit times for customers and balancing stock levels.

**SFS-Enabled Stores:** Currently 87 of 312 stores are SFS-enabled. Eligibility is based on store size, backroom capacity, and staffing levels.

### 6.1 SFS Workflow

1. New SFS orders appear in the **StoreOps App** (available on store-issued iPads and handheld devices).
2. The SFS associate receives a pick list. Items must be picked within **60 minutes** of the order appearing in the queue.
3. Items are packed using SFS-designated materials located in the backroom SFS station.
4. Labels are printed from the SFS label printer — do not use regular store printers.
5. Packed orders are placed in the designated carrier pickup zone by **1:00 PM** for same-day carrier pickup (or as scheduled for that store location).
6. The order is marked as shipped in StoreOps, which triggers the customer shipping notification.

### 6.2 SFS Inventory Conflicts

If a picked item is damaged or not actually in stock (inventory inaccuracy), the associate must:

1. Mark the item as "Unable to Fulfill" in StoreOps.
2. The OMS will automatically attempt to reroute the order to the nearest FC or SFS-enabled store.
3. Do not cancel the order manually — let the system reroute first.
4. If rerouting fails within 2 hours, the system will cancel and refund the order automatically.

---

## 7. Same-Day & Express Delivery

Same-day delivery is available in **42 metro markets** as of March 2025. Orders must be placed by **12:00 PM local time** to qualify for same-day delivery. Orders placed after 12:00 PM will default to next-day delivery if selected.

**Same-day delivery is fulfilled from:**
- The nearest SFS-enabled store within 15 miles of the delivery address, OR
- FC-CHI, FC-ATL, FC-LAX for select metro areas with rapid transit coverage

**Delivery partners:** Roadie (primary), GoShip (secondary for overflow)

Delivery windows offered to customers: **10 AM–2 PM, 12 PM–4 PM, 2 PM–6 PM, 4 PM–8 PM**

Associates handling same-day orders should prioritize them above standard SFS orders. Same-day orders are flagged in StoreOps with a yellow "EXPRESS" badge.

---

## 8. Packaging Standards

Proper packaging protects product integrity and minimizes damage claims. Follow all packaging specifications as directed by the WMS packing screen.

### 8.1 Box Selection Guidelines

| Item Weight | Recommended Box | Notes |
|---|---|---|
| Under 1 lb | Poly mailer or small box (S1) | Use poly mailer where item is non-fragile |
| 1–5 lbs | Small box (S1) or medium box (M1) | |
| 5–20 lbs | Medium box (M1) or large box (L1) | |
| 20–50 lbs | Large box (L1) or double-walled (DW1) | |
| Over 50 lbs | Double-walled (DW1) or freight packaging | Requires supervisor sign-off |

### 8.2 Void Fill & Protection

- Fragile items must be wrapped in minimum 2 inches of bubble wrap or foam padding.
- All boxes must be filled to prevent item movement — use kraft paper or air pillows to fill void space.
- Do not overfill boxes; lids should close flat without bulging.
- Glass, ceramics, and mirrors require double-boxing with at least 2 inches of foam between inner and outer boxes.

### 8.3 Branded Packaging

Acme Retail-branded boxes and mailers are used for standard shipments. Unbranded brown boxes are used for discreet shipping (customer-selected option) and B2B orders. Do not use competitor-branded packaging under any circumstances.

---

## 9. Labeling Requirements

All shipments must have a compliant shipping label generated through AcmeShip.

**Label must include:**
- Recipient name and delivery address
- Acme Retail return address (FC or store, as applicable)
- Carrier barcode and tracking number
- Order number (in human-readable format below barcode)
- Package weight
- Service level (e.g., "UPS Ground," "Priority Mail")

**Label placement:**
- Apply to the largest flat face of the box.
- Do not place over seams, edges, or packing tape.
- Label must be clearly legible — replace any smudged or incomplete labels before handoff to carrier.

**Packing slip:** A packing slip must be included inside every package. The packing slip is generated automatically by AcmeShip and printed simultaneously with the label.

---

## 10. Hazardous & Restricted Materials

Certain products require special handling and labeling for shipment. The OMS will flag these automatically, but associates should be familiar with the categories.

| Category | Examples | Requirement |
|---|---|---|
| Lithium batteries (standalone) | Power banks, spare laptop batteries | Ground shipment only; special labeling |
| Lithium batteries (in device) | Laptops, phones, cameras | Air eligible with ORM-D labeling; quantity limits |
| Flammable liquids | Nail polish, perfume (>4 oz) | Ground only; hazmat label required |
| Aerosols | Spray paint, compressed air cans | Ground only; ORM-D label |
| Ammunition | Restricted items | Cannot ship via standard carrier |
| Dry ice | Perishable cold-packs | Special UPS/FedEx service; quantity limits |

Associates should never ship a hazmat-flagged item without completing the hazmat checkout step in AcmeShip. Failure to comply with carrier hazmat rules may result in package refusal, fines, and regulatory action.

---

## 11. Order Tracking & Customer Communication

Acme Retail's OMS automatically sends the following notifications to customers:

| Event | Notification Channel |
|---|---|
| Order confirmed | Email + App push notification |
| Order shipped (label created) | Email + SMS + App push |
| Out for delivery | SMS + App push |
| Delivered | Email + SMS + App push |
| Delivery exception (delay, failed attempt) | Email + SMS |
| Return label issued | Email |
| Refund processed | Email |

Customers can track orders at **acmeretail.com/track** or via the Acme app using their order number or email address. Associates can access full tracking details in the OMS order view. For carrier-specific tracking, use the carrier account codes listed in Section 2.

---

## 12. Lost, Delayed, or Damaged Shipments

### 12.1 Delayed Shipments

A shipment is considered delayed when it has not moved in the carrier's tracking system for more than:
- **3 business days** for domestic ground shipments
- **2 business days** for air/expedited shipments
- **5 business days** for international shipments

Associates should initiate a carrier trace in OMS. If the trace does not resolve within 48 hours, escalate to the Logistics Operations team.

### 12.2 Lost Shipments

A shipment is declared lost when:
- Carrier confirms loss, OR
- Tracking has not updated for **7 business days** (domestic) or **10 business days** (international) past the expected delivery date.

For lost shipments, Customer Care should offer the customer a full re-shipment or refund within **1 business day** of loss confirmation. Do not wait for the carrier claim to be settled before assisting the customer.

### 12.3 Damaged Shipments

If a customer receives a damaged item:
1. Advise the customer to keep all packaging and take photos.
2. Initiate a damage claim in OMS within **5 business days** of delivery.
3. Offer the customer a replacement or full refund immediately — do not wait for claim resolution.
4. The Logistics team will file the carrier claim and coordinate any insurance recovery.

---

## 13. Return Logistics

### 13.1 Prepaid Return Labels

Return labels are generated via OMS when a customer initiates a return online or via the app. All prepaid return labels use **UPS Ground** by default. Exceptions (oversized, freight) are handled by the Logistics team.

### 13.2 Return Routing

Returned packages are routed to the nearest FC based on the return address:

| Return Drop-Off Region | Routed to FC |
|---|---|
| Midwest / Great Plains | FC-CHI |
| Southeast / Mid-Atlantic | FC-ATL |
| South Central | FC-DAL |
| West Coast | FC-LAX |
| Northeast | FC-NJY |
| Canada | FC-TOR |

### 13.3 Returned Inventory Processing

Returns received at the FC are processed within **2 business days** of arrival:

1. Package is scanned upon receipt and matched to the RMA in OMS.
2. Item is inspected against condition criteria.
3. Item is sorted into: **Resaleable, Refurbish, Vendor Return, or Destroy**.
4. Refund is triggered in OMS upon inspection completion.

---

## 14. B2B & Wholesale Shipments

B2B orders are managed by the Wholesale Operations team and follow different SLAs and carrier arrangements than standard consumer orders.

- **Order lead time:** Minimum 3 business days; standard 5–7 business days.
- **Minimum order:** $500 net (subject to account agreement).
- **Carrier:** Acme Private Fleet (within 150-mile FC radius) or XPO Logistics LTL for longer distances.
- **Packing:** B2B orders are packed on pallets, shrink-wrapped, and labeled with pallet labels in addition to individual carton labels.
- **Documentation:** All B2B shipments include a commercial invoice, packing list, and Bill of Lading (BOL). BOL must be signed by the carrier driver before departure.
- **Proof of Delivery:** Signed delivery confirmation is required for all B2B orders and must be uploaded to the B2B order in OMS within 48 hours of delivery.

---

## 15. Peak Season Protocols

Peak shipping periods require adjusted operations. The following periods are designated as peak seasons:

| Season | Period | Expected Volume Increase |
|---|---|---|
| Back-to-School | July 15 – August 31 | +35% |
| Holiday | November 1 – December 31 | +110% |
| Post-Holiday Returns | January 1 – January 31 | +60% |
| Spring Home | March 15 – April 30 | +25% |

During peak periods:
- Extended FC operating hours (5:00 AM – 12:00 AM, 7 days/week).
- Seasonal associates are onboarded and trained at least 2 weeks before peak start.
- Carrier cutoff times move earlier by 30 minutes — review the current peak calendar posted at each packing station.
- All SFS stores increase their same-day order processing capacity from 10 to 20 orders per hour target.
- The Logistics Operations Bridge (call bridge x5200) is active 7 AM–10 PM daily during Holiday peak.

---

## 16. Carrier Cutoff Times

Packages must be scanned by carriers by these times to guarantee the posted service level. These are standard times — **verify the current schedule posted at your station, as times shift during peak season.**

| Service | Carrier | FC Cutoff Time (local) | SFS Cutoff Time (local) |
|---|---|---|---|
| Same-Day Delivery | Roadie/GoShip | 1:00 PM | 12:30 PM |
| Overnight / Next Day Air | UPS / FedEx | 3:00 PM | 1:00 PM |
| 2-Day Air | UPS / FedEx | 3:30 PM | 1:00 PM |
| Ground (Standard) | UPS / FedEx / USPS | 5:00 PM | 2:00 PM |
| International | DHL | 2:00 PM | N/A (FC only) |
| LTL Freight | XPO | 12:00 PM (scheduled pickup) | N/A |

Orders that miss the carrier cutoff are held and shipped on the next business day. The OMS will automatically update the estimated delivery date and send the customer a revised notification.

---

*This document is reviewed and updated quarterly. For the latest version, visit the Logistics section of AcmeConnect. For urgent operational questions, contact Logistics Operations at logistics@acmeretail.com or x5100.*