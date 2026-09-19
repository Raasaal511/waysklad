import { api } from '../../shared/api/client'
import { customerAuthHeader } from '../auth/customerApi'

export type ReviewSort = 'date_desc' | 'date_asc' | 'rating_desc' | 'rating_asc' | 'useful'

export interface ReviewTag {
  code: string
  label: string
}

export interface ReviewTagWithCount extends ReviewTag {
  count: number
}

export interface Review {
  id: number
  product_id: number
  rating: number
  text: string
  author_name: string
  photo: string
  photos: string[]
  tags: ReviewTag[]
  likes: number
  dislikes: number
  my_vote: 0 | 1 | -1
  created_at: string | null
  is_hidden: boolean | null
}

export interface RatingDistribution {
  '5': number
  '4': number
  '3': number
  '2': number
  '1': number
}

export interface ReviewPhotoRef {
  url: string
  review_id: number
}

export interface ReviewsPage {
  reviews: Review[]
  total: number
  average_rating: number
  reviews_count: number
  rating_distribution: RatingDistribution
  with_photos_count: number
  tags: ReviewTagWithCount[]
  photos: ReviewPhotoRef[]
}

export interface ReviewEligibility {
  can_review: boolean
  request_id: number | null
  reason: 'ok' | 'no_purchase' | 'already_reviewed'
}

export interface ReviewsQueryParams {
  sort?: ReviewSort
  rating?: number
  with_photos?: boolean
  tag?: string
  limit?: number
  offset?: number
}

function reviewsQuery(params: ReviewsQueryParams) {
  const search = new URLSearchParams()
  if (params.sort) search.set('sort', params.sort)
  if (params.rating != null) search.set('rating', String(params.rating))
  if (params.with_photos) search.set('with_photos', 'true')
  if (params.tag) search.set('tag', params.tag)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export function getProductReviews(slug: string, productId: number, params: ReviewsQueryParams = {}) {
  return api.get<ReviewsPage>(
    `/storefront/${encodeURIComponent(slug)}/products/${productId}/reviews${reviewsQuery(params)}`,
    { headers: customerAuthHeader() },
  )
}

export function getReviewEligibility(slug: string, productId: number) {
  return api.get<ReviewEligibility>(
    `/storefront/${encodeURIComponent(slug)}/products/${productId}/reviews/eligibility`,
    { headers: customerAuthHeader() },
  )
}

export function createReview(input: {
  storefront_request_id: number
  product_id: number
  rating: number
  text: string
  photos: string[]
  tags: string[]
}) {
  return api.post<Review>('/reviews', input, { headers: customerAuthHeader() })
}

export function uploadReviewPhoto(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<{ url: string }>('/reviews/photos', form, { headers: customerAuthHeader() })
}

export function voteReview(reviewId: number, value: 1 | -1 | 0) {
  return api.put<{ likes: number; dislikes: number; my_vote: 0 | 1 | -1 }>(
    `/reviews/${reviewId}/vote`,
    { value },
    { headers: customerAuthHeader() },
  )
}

export function getReviewTags() {
  return api.get<ReviewTag[]>('/reviews/tags')
}

// --- Панель владельца ---

export interface OwnerReview extends Review {
  product_name?: string
}

export function getOwnerProductReviews(productId: number) {
  return api.get<{ reviews: Review[] }>(`/reviews/product/${productId}`)
}

export type OwnerReviewsStatus = 'all' | 'visible' | 'hidden'

export async function listOwnerReviews(params: { status?: OwnerReviewsStatus; limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<{ reviews: OwnerReview[]; total: number }>(`/reviews${qs ? `?${qs}` : ''}`)
}

export function hideReview(reviewId: number) {
  return api.post<Review>(`/reviews/${reviewId}/hide`)
}

export function unhideReview(reviewId: number) {
  return api.post<Review>(`/reviews/${reviewId}/unhide`)
}
