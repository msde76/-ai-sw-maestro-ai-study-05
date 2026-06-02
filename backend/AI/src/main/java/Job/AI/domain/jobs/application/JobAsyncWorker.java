package Job.AI.domain.jobs.application;

import Job.AI.domain.jobs.converter.JobConverter;
import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.List;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class JobAsyncWorker {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    private static final String TASK_KEY_PREFIX = "job:task:";

    // application.yml에서 주소 값을 동적으로 주입받습니다.
    @Value("${app.ai.server-url}")
    private String aiServerUrl;

    public JobAsyncWorker(StringRedisTemplate redisTemplate, ObjectMapper objectMapper) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.restClient = RestClient.create();
    }

    @Async
    public void processAiRecommendation(String taskId, JobRequestDTO.TaskInfoDTO taskInfo) {
        String redisKey = TASK_KEY_PREFIX + taskId;

        try {
            log.info("[Task {}] AI 서버({})에 추천 요청 전송 시작...", taskId, aiServerUrl);

            // 1. 하드코딩된 주소 대신 주입받은 aiServerUrl 변수를 사용합니다.
            List<JobResponseDTO.JobDataDTO> resultData = restClient.post()
                    .uri(aiServerUrl)
                    .body(taskInfo)
                    .retrieve()
                    .body(new ParameterizedTypeReference<List<JobResponseDTO.JobDataDTO>>() {});

            log.info("[Task {}] AI 서버 응답 수신 완료. 추출된 추천 공고 수: {}", taskId, resultData != null ? resultData.size() : 0);

            // 2. 상태 처리 로직
            JobResponseDTO.TaskStatusDTO completedStatus;
            if (resultData == null || resultData.isEmpty()) {
                completedStatus = JobConverter.toTaskStatusDTO(
                        "EMPTY",
                        "적합도 0.7 이상의 공고를 찾지 못했습니다. 조건을 완화해 보세요.",
                        List.of()
                );
            } else {
                completedStatus = JobConverter.toTaskStatusDTO(
                        "COMPLETED",
                        "사용자 맞춤형 채용공고 추천이 완료되었습니다.",
                        resultData
                );
            }

            // 3. Redis 최종 업데이트
            redisTemplate.opsForValue().set(redisKey, objectMapper.writeValueAsString(completedStatus), 10, TimeUnit.MINUTES);
            log.info("[Task {}] 추천 완료! Redis 업데이트 성공.", taskId);

        } catch (RestClientException e) {
            log.error("[Task {}] AI 서버 통신 중 에러 발생: {}", taskId, e.getMessage());
            saveErrorStatusToRedis(redisKey);
        } catch (Exception e) {
            log.error("[Task {}] AI 추천 처리 중 알 수 없는 에러 발생: {}", taskId, e.getMessage());
            saveErrorStatusToRedis(redisKey);
        }
    }

    private void saveErrorStatusToRedis(String redisKey) {
        JobResponseDTO.TaskStatusDTO errorStatus = JobConverter.toTaskStatusDTO(
                "ERROR",
                "AI 서버와 통신하는 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                null
        );
        try {
            redisTemplate.opsForValue().set(redisKey, objectMapper.writeValueAsString(errorStatus), 10, TimeUnit.MINUTES);
        } catch (JsonProcessingException ex) {
            log.error("Redis 에러 상태 저장 실패", ex);
        }
    }
}