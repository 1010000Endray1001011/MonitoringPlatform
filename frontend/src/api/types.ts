// Thin re-export layer over the generated schema — every other file
// imports request/response shapes from here rather than reaching into
// schema.ts's `components["schemas"][...]` indexing directly, so a
// regeneration that changes the generated structure only needs fixing up
// in one place.
import type { components } from './schema'

export type AccessToken = components['schemas']['AccessToken']
export type TokenObtainPairRequest = components['schemas']['TokenObtainPairRequest']
export type RegisterRequest = components['schemas']['RegisterRequest']
export type RegisterResponse = components['schemas']['Register']
