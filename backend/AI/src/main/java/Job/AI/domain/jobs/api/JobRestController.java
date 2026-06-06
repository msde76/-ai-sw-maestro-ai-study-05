package Job.AI.domain.jobs.api;

import Job.AI.domain.jobs.application.JobService;
import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;
import Job.AI.global.BaseResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/jobs/recommend")
@RequiredArgsConstructor
public class JobRestController {

    private final JobService jobService;

    @PostMapping("/tasks")
    @Operation(summary = "채용공고 추천 작업 생성 API", description = "요청을 접수하고 작업 ID를 즉시 반환합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "OK")
    })
    public BaseResponse<JobResponseDTO.TaskCreationDTO> setTask(
            @RequestBody JobRequestDTO.TaskInfoDTO taskInfo
    ) {
        JobResponseDTO.TaskCreationDTO result = jobService.setTask(taskInfo);
        return BaseResponse.onAccepted("AI 에이전트가 채용공고 분석을 시작했습니다.", result);
    }

    @GetMapping("/tasks/{taskId}")
    @Operation(summary = "채용공고 추천 작업 상태 조회 API", description = "작업 ID로 진행 상태와 최종 결과를 조회합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "OK")
    })
    public BaseResponse<List<JobResponseDTO.JobDataDTO>> getTaskStatus(
            @PathVariable("taskId") String taskId
    ) {
        JobResponseDTO.TaskStatusDTO result = jobService.getTaskStatus(taskId);
        return BaseResponse.of(result.getStatus(), result.getMessage(), result.getData());
    }
}
