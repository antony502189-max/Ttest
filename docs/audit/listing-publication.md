# Listing publication contract audit

## Production request sequence

1. `GET /api/v1/auth/email-verification/status`
2. `POST /api/v1/listings` with `Idempotency-Key`
   - authorizes the canonical database user;
   - checks email verification, moderation policy, idempotent replay, and creation limits;
   - updates the selected contact profile fields and creates the listing, room details, status history, notification, and catalog version in one database transaction.
3. For each browser-local image: `POST /api/v1/uploads`.
4. `PUT /api/v1/listings/{id}/images` once, with ordered owned asset IDs.
5. Browser-local media cleanup after the server returns the final image list.

`PATCH /api/v1/users/me` is no longer part of creation. It remains part of explicit profile editing and listing editing, which are separate user actions.

## Field mapping

All rows pass through `PublishPage.toListing()` and `src/api/listings.ts:listingPayload()` before `ListingWrite` validation. `null` is sent for nullable scalar fields; absent draft-only values are never sent as server-owned fields.

| UI draft field | `Listing` field | JSON / `ListingWrite` field | Database target |
|---|---|---|---|
| `title` | `title` | `title` | `listings.title` |
| fixed municipality selector `city` | `city` | `city` | `listings.city` |
| `area` | `area` | `area` | `listings.area` |
| private `street` draft | `street` | `street` | `listings.street` |
| private `postcode` draft | `postcode` | `postcode` | `listings.postcode` |
| area-derived public label | `approximateAddress` | `approximateAddress` | `listings.approximate_address` |
| `rentalMode` | `rentalMode` | `rentalMode` | `listings.rental_mode` |
| `monthlyPrice` | `monthlyPrice` | `monthlyPrice` | `listings.monthly_price` |
| `nightlyPrice` | `nightlyPrice` | `nightlyPrice` | `listings.nightly_price` |
| `weeklyPrice` | `weeklyPrice` | `weeklyPrice` | `listings.weekly_price` |
| `roomType` | `roomType` | `roomType` | `listings.room_type` |
| `availableFrom` | `availableFrom` | `availableFrom` | `listings.available_from` |
| blank `availableUntil` | omitted on `Listing` | `availableUntil: null` | `listings.available_until` |
| `minimumStayMonths` | `minimumStayMonths` | `minimumStayMonths` | `listings.minimum_stay_months` |
| `minimumNights` | holiday value or absent | `minimumNights` / `null` | `listings.minimum_nights` |
| `depositAmount` | `depositAmount` | `depositAmount` | `listings.deposit_amount` |
| `billsIncluded` | `billsIncluded` | `billsIncluded` | `listings.bills_included` |
| `billsNote` or included label | `bills` | `billsText` | `listings.bills_text` |
| `bathroom` | `bathroom` | `bathroom` | `listings.bathroom` |
| `kitchen` | `kitchen` | `kitchen` | `listings.kitchen` |
| `furnished` | `furnished` | `furnished` | `listings.furnished` |
| `roomSizeM2` | `roomSizeM2` | `roomSizeM2` | `listings.room_size_m2` |
| `bedroomCount` | `bedroomCount` | `bedroomCount` | `listings.bedroom_count` |
| `currentResidents` | `currentResidents` | `currentResidents` | `listings.current_residents` |
| `roomCapacity` | `roomCapacity` | `roomCapacity` | `listings.room_capacity` |
| `shower` | `shower` | `shower` | `listings.shower` |
| `tenantRequirement` | `tenantRequirement` | `tenantRequirement` | `listings.tenant_requirement` |
| `smokingAllowed` | `smokingAllowed` | `smokingAllowed` | `listings.smoking_allowed` |
| `petsAllowed` | `petsAllowed` | `petsAllowed` | `listings.pets_allowed` |
| `childrenAllowed` | `childrenAllowed` | `childrenAllowed` | `listings.children_allowed` |
| `empadronamientoAllowed` | `empadronamientoAllowed` | `empadronamientoAllowed` | `listings.empadronamiento_allowed` |
| `homeSizeM2` | `homeSizeM2` | `homeSizeM2` | `listing_room_details.home_size_m2` |
| `bathroomCount` | `bathroomCount` | `bathroomCount` | `listing_room_details.bathroom_count` |
| `rentalUnit` | `rentalUnit` | `rentalUnit` | `listing_room_details.rental_unit` |
| `bedType` | `bedType` | `bedType` | `listing_room_details.bed_type_v2` plus legacy-compatible mirror |
| `bedCount` | `bedCount` | `bedCount` | `listing_room_details.bed_count` |
| `currentRoomResidents` | `currentRoomResidents` | `currentRoomResidents` | `listing_room_details.current_room_residents` |
| derived `roomCapacity - currentRoomResidents` | `availableSpots` | not writable | derived in API response |
| `toilet` | `toilet` | `toilet` | `listing_room_details.toilet` |
| `householdGender` | `householdGender` | `householdGender` | `listing_room_details.household_gender` |
| `householdHasChildren` | `householdHasChildren` | `householdHasChildren` | `listing_room_details.household_has_children` |
| `heatingType` | `heatingType` | `heatingType` | `listing_room_details.heating_type` |
| `accessible` | `accessible` | `accessible` | `listing_room_details.accessible` |
| `floor` | `floor` | `floor` | `listing_room_details.floor` |
| `couplesAllowed` | `couplesAllowed` | `couplesAllowed` | `listing_room_details.couples_allowed` |
| `acceptedTenantTypes` | `acceptedTenantTypes` | `acceptedTenantTypes` | `listing_room_details.accepted_tenant_types` |
| derived critical rules | `restrictions` | `restrictions` | `listings.restrictions` JSONB |
| normalized equipment selections | `amenities` | `amenities` | `listings.amenities` JSONB |
| privacy-jittered point | `coordinates.lat` | `latitude` | `listings.location` geography |
| privacy-jittered point | `coordinates.lng` | `longitude` | `listings.location` geography |
| private selected point | `exactCoordinates.lat` | `exactLatitude` | `listings.exact_location` geography |
| private selected point | `exactCoordinates.lng` | `exactLongitude` | `listings.exact_location` geography |
| `description` | `description` | `description` | `listings.description` |
| `rules` | `homeDescription` | `homeDescription` | `listings.home_description` |
| fixed product value | `advertiserType` | `advertiserType` | `listings.advertiser_type` |
| `expiresAt` date | `expiresAt` | UTC `expiresAt` / `null` | `listings.expires_at` |
| `contactName` | `owner.name` | `contactName` | `users.name` in the listing transaction |
| `contactPhone` | `contactPhone` | `contactPhone` | `users.phone` in the listing transaction |
| `contactWhatsapp` | `contactWhatsapp` | `contactWhatsapp` | `users.whatsapp` in the listing transaction |
| `showPhone` | `showPhone` | `showPhone` | `users.show_phone` in the listing transaction |
| `showWhatsApp` | `showWhatsApp` | `showWhatsApp` | `users.show_whatsapp` in the listing transaction |

The create schema forbids extra fields. `ownerUserId`, `status`, `promoted`, `isExternal`, and provenance `source` cannot be assigned by the publication client.

## Authorization matrix

| Actor/state | Result |
|---|---|
| anonymous, invalid/deleted/blocked identity | `401` |
| tenant or legacy admin role without active admin grant | `403 HOST_ACCOUNT_REQUIRED` |
| host or active Google-backed admin grant | allowed, subject to the remaining checks |
| unverified host | `409 EMAIL_VERIFICATION_REQUIRED` |
| active full/publish restriction | `403 PUBLISHING_RESTRICTED` |
| active view-only restriction | publication allowed |
| expired restriction | publication allowed |
| active listing limit | `409 ACTIVE_LISTING_LIMIT_REACHED` |
| daily creation limit | `429 DAILY_LISTING_LIMIT_REACHED` |

## Media and transaction decision

`POST /listings` can succeed while a later upload or image replacement fails because browser uploads are separate HTTP requests. This is intentional: the UI reports that the listing was created and directs the host to retry images from **Mis anuncios**. It never reports the whole publication as failed. The durable publication key prevents that retry path from creating a second listing.

Listing, room details, status history, notification/outbox work, contact profile changes, and catalog invalidation commit together. An exception before commit rolls all of them back. Image replacement separately locks the listing and assets, checks listing ownership and media ownership/kind/deletion state, replaces ordering and cover state, marks detached media for cleanup, and commits once.
