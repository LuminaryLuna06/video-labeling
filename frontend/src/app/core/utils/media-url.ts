import { environment } from '../../../environments/environment';
import { ImageItem, VideoItem } from '../models';
import type { SimilarImageMatch, FrameSimilarImages } from '../services/video.service';

export function toAbsoluteUrl<T extends string | undefined | null>(path: T): T {
    if (!path) return path;
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    if (path.startsWith('data:') || path.startsWith('blob:')) return path;
    if (path.startsWith('//')) return path;
    if (!path.startsWith('/')) return path;
    return (environment.baseUrl + path) as T;
}

export function normalizeVideo(video: VideoItem): VideoItem {
    return {
        ...video,
        url: toAbsoluteUrl(video.url),
        thumbnail_url: toAbsoluteUrl(video.thumbnail_url),
    };
}

export function normalizeImage(image: ImageItem): ImageItem {
    return {
        ...image,
        url: toAbsoluteUrl(image.url),
        thumbnail_url: toAbsoluteUrl(image.thumbnail_url),
    };
}

export function normalizeSimilarImage(match: SimilarImageMatch): SimilarImageMatch {
    return { ...match, url: toAbsoluteUrl(match.url) };
}

export function normalizeFrameSimilarImages(frame: FrameSimilarImages): FrameSimilarImages {
    return { ...frame, images: frame.images.map(normalizeSimilarImage) };
}
