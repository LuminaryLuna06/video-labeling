import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * Interceptor tự động thêm baseUrl vào phía trước mọi request HTTP.
 * - Production: baseUrl = 'https://your-api-domain.com' → request đi thẳng đến server
 * - Development: baseUrl = '' → request giữ nguyên path '/api/...' và được proxy xử lý
 */
export const baseUrlInterceptor: HttpInterceptorFn = (req, next) => {
    const baseUrl = environment.baseUrl;

    // Nếu không có baseUrl (dev) hoặc request đã là URL tuyệt đối thì bỏ qua
    if (!baseUrl || req.url.startsWith('http')) {
        return next(req);
    }

    const apiReq = req.clone({
        url: `${baseUrl}${req.url}`,
    });

    return next(apiReq);
};
