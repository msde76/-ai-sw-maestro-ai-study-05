package Job.AI.domain.jobs.application;

import Job.AI.domain.jobs.converter.JobConverter;
import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class JobServiceImpl implements JobService {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final JobAsyncWorker jobAsyncWorker;

    private static final String TASK_KEY_PREFIX = "job:task:";
    private static final int TASK_TTL_MINUTES = 10;
    private static final String PROCESSING_MESSAGE = "채용공고를 검색하고 자기소개서와 비교 분석 중입니다.";

    @Override
    public JobResponseDTO.TaskCreationDTO setTask(JobRequestDTO.TaskInfoDTO taskInfo) {
        String taskId = UUID.randomUUID().toString();
        String redisKey = TASK_KEY_PREFIX + taskId;

        JobResponseDTO.TaskStatusDTO initialStatus = JobConverter.toTaskStatusDTO(
                "PROCESSING",
                PROCESSING_MESSAGE,
                null
        );

        try {
            redisTemplate.opsForValue().set(
                    redisKey,
                    objectMapper.writeValueAsString(initialStatus),
                    TASK_TTL_MINUTES,
                    TimeUnit.MINUTES
            );
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Redis 작업 상태 직렬화에 실패했습니다.", e);
        }

        jobAsyncWorker.processAiRecommendation(taskId, taskInfo);

        return JobConverter.toTaskCreationDTO(taskId);
    }

    @Override
    public JobResponseDTO.TaskStatusDTO getTaskStatus(String taskId) {
        String redisKey = TASK_KEY_PREFIX + taskId;
        String statusJson = redisTemplate.opsForValue().get(redisKey);

        if (statusJson == null) {
            throw new IllegalArgumentException("존재하지 않거나 만료된 작업입니다.");
        }

        try {
            return objectMapper.readValue(statusJson, JobResponseDTO.TaskStatusDTO.class);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Redis 작업 상태 역직렬화에 실패했습니다.", e);
        }
    }
}
