package Job.AI.global;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**") // 프로젝트의 모든 API 엔드포인트에 대해 CORS 적용
                // MVP 로컬 테스트용: 모든 오리진 허용 (또는 프론트엔드 로컬 주소만 명시)
                .allowedOriginPatterns("*")
                .allowedOrigins("http://localhost:3000", "http://localhost:5173") // 프론트엔드 주소가 확정되면 이렇게 제한하는 것이 좋습니다.
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS") // 허용할 HTTP 메서드
                .allowedHeaders("*") // 모든 헤더 허용
                .allowCredentials(true) // 쿠키나 인증 정보(Authorization 헤더 등)를 포함한 요청 허용
                .maxAge(3600); // Preflight 요청의 결과를 1시간(3600초) 동안 캐시하여 통신 비용 절감
    }
}