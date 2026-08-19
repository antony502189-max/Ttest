# Customer priority filters and location UX

Implementation scope requested by the customer:

- Prioritize price, move-in date, private shower/toilet/kitchen, fully private room zone, air conditioning, bed type, street-facing window, and smoking.
- Add a structured bathroom/toilet preset filter including private toilet + shared shower.
- Keep terrace, pool, garden, elevator, cleaning, accessibility and floor as secondary filters.
- Use explicit floor values: any, basement, 1, 2, 3, 4+, top floor.
- Preserve an optional move-out date.
- Improve listing publication location selection with address autocomplete and map-based coordinate selection while keeping public location approximate.
- Keep Tenerife as the supported geography and preserve the approved product design.

This note documents scope only; executable behavior is covered by the implementation and automated tests.