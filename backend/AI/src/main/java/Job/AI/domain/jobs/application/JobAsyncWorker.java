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

import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class JobAsyncWorker {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    private static final String TASK_KEY_PREFIX = "job:task:";
    private static final double MIN_SUITABILITY_SCORE = 0.7;
    private static final int TASK_TTL_MINUTES = 10;

    private static final String COMPLETED_MESSAGE =
            "사용자에게 적합한 채용공고 추천이 완료되었습니다. 지원 전 원문 링크에서 최신 상태를 확인하세요.";
    private static final String EMPTY_MESSAGE =
            "적합도 0.7 이상인 공고를 찾지 못했습니다. 희망 조건을 완화해 다시 시도해보세요.";
    private static final String ERROR_MESSAGE =
            "AI 서버와 통신하는 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.";

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
            log.info("[Task {}] AI server({}) recommendation request started.", taskId, aiServerUrl);

            List<JobResponseDTO.JobDataDTO> resultData = restClient.post()
                    .uri(aiServerUrl)
                    .body(taskInfo)
                    .retrieve()
                    .body(new ParameterizedTypeReference<List<JobResponseDTO.JobDataDTO>>() {});

            List<JobResponseDTO.JobDataDTO> normalizedData = normalizeRecommendations(resultData);
            log.info(
                    "[Task {}] AI server response received. raw={}, normalized={}",
                    taskId,
                    resultData != null ? resultData.size() : 0,
                    normalizedData.size()
            );

            JobResponseDTO.TaskStatusDTO completedStatus = createCompletionStatus(normalizedData);

            redisTemplate.opsForValue().set(
                    redisKey,
                    objectMapper.writeValueAsString(completedStatus),
                    TASK_TTL_MINUTES,
                    TimeUnit.MINUTES
            );
            log.info("[Task {}] Recommendation finished. Redis status updated.", taskId);

        } catch (RestClientException e) {
            log.error("[Task {}] AI server communication failed: {}", taskId, e.getMessage());
            saveErrorStatusToRedis(redisKey);
        } catch (Exception e) {
            log.error("[Task {}] Unexpected recommendation error: {}", taskId, e.getMessage());
            saveErrorStatusToRedis(redisKey);
        }
    }

    private List<JobResponseDTO.JobDataDTO> normalizeRecommendations(List<JobResponseDTO.JobDataDTO> resultData) {
        if (resultData == null || resultData.isEmpty()) {
            return List.of();
        }

        return resultData.stream()
                .filter(jobData -> jobData != null && jobData.getSuitabilityScore() != null)
                .filter(jobData -> jobData.getSuitabilityScore() >= MIN_SUITABILITY_SCORE)
                .sorted(Comparator.comparing(JobResponseDTO.JobDataDTO::getSuitabilityScore).reversed())
                .toList();
    }

    private JobResponseDTO.TaskStatusDTO createCompletionStatus(List<JobResponseDTO.JobDataDTO> normalizedData) {
        if (normalizedData == null || normalizedData.isEmpty()) {
            return JobConverter.toTaskStatusDTO("EMPTY", EMPTY_MESSAGE, List.of());
        }

        return JobConverter.toTaskStatusDTO("COMPLETED", COMPLETED_MESSAGE, normalizedData);
    }

    private void saveErrorStatusToRedis(String redisKey) {
        JobResponseDTO.TaskStatusDTO errorStatus = JobConverter.toTaskStatusDTO(
                "ERROR",
                ERROR_MESSAGE,
                null
        );
        try {
            redisTemplate.opsForValue().set(
                    redisKey,
                    objectMapper.writeValueAsString(errorStatus),
                    TASK_TTL_MINUTES,
                    TimeUnit.MINUTES
            );
        } catch (JsonProcessingException ex) {
            log.error("Failed to save Redis error status.", ex);
        }
    }
}
