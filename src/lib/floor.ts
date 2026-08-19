import type { FloorLevel, Listing } from '@/types'

const FLOOR_RANK: Record<FloorLevel, number> = {
  basement: 0,
  '1': 1,
  '2': 2,
  '3': 3,
  '4+': 4,
  top: 5,
}

export function floorRank(floor: Listing['floor']) {
  return floor == null ? null : FLOOR_RANK[floor]
}

export function compareListingFloors(
  left: Pick<Listing, 'id' | 'floor'>,
  right: Pick<Listing, 'id' | 'floor'>,
  direction: 'asc' | 'desc',
) {
  const leftRank = floorRank(left.floor)
  const rightRank = floorRank(right.floor)
  if (leftRank == null && rightRank == null) return left.id.localeCompare(right.id)
  if (leftRank == null) return 1
  if (rightRank == null) return -1
  const delta = direction === 'asc' ? leftRank - rightRank : rightRank - leftRank
  return delta || left.id.localeCompare(right.id)
}
