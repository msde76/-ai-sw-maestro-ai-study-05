package Job.AI.domain.jobs.application;

import Job.AI.domain.jobs.converter.JobConverter;
import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class JobServiceImpl implements JobService {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final JobAsyncWorker jobAsyncWorker; // 비동기 워커 의존성 주입

    private static final String TASK_KEY_PREFIX = "job:task:";

    @Override
    public JobResponseDTO.TaskCreationDTO setTask(JobRequestDTO.TaskInfoDTO taskInfo) {
        // 1. 고유 Task ID 생성
        String taskId = UUID.randomUUID().toString();
        String redisKey = TASK_KEY_PREFIX + taskId;

        // 2. 초기 상태를 Redis에 저장 (PROCESSING)
        JobResponseDTO.TaskStatusDTO initialStatus = JobConverter.toTaskStatusDTO(
                "PROCESSING",
                "PathsDog MCP에서 공고를 검색하고 자소서와 비교 중입니다...",
                null
        );

        try {
            // Redis에 JSON 형태로 저장 (TTL: 10분 설정 - 작업이 너무 오래 메모리에 남지 않도록)
            redisTemplate.opsForValue().set(redisKey, objectMapper.writeValueAsString(initialStatus), 10, TimeUnit.MINUTES);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Redis 데이터 직렬화 실패", e);
        }

        // 3. 비동기 스레드에 AI 호출 및 분석 로직 위임 (메인 스레드는 기다리지 않음!)
        jobAsyncWorker.processAiRecommendation(taskId, taskInfo);

        // 4. 프론트엔드에 즉시 taskId 반환
        return JobConverter.toTaskCreationDTO(taskId);
    }

    @Override
    public JobResponseDTO.TaskStatusDTO getTaskStatus(String taskId) {
        String redisKey = TASK_KEY_PREFIX + taskId;
        String statusJson = redisTemplate.opsForValue().get(redisKey);

        // Redis에 해당 Task가 없을 경우 예외 처리
        if (statusJson == null) {
            throw new IllegalArgumentException("존재하지 않거나 만료된 작업입니다.");
        }

        try {
            return objectMapper.readValue(statusJson, JobResponseDTO.TaskStatusDTO.class);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Redis 데이터 역직렬화 실패", e);
        }
    }
}
