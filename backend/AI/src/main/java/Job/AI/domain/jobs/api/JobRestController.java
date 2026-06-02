package Job.AI.domain.jobs.api;

import Job.AI.domain.jobs.application.JobService;
import Job.AI.domain.jobs.dto.JobRequestDTO;
import Job.AI.domain.jobs.dto.JobResponseDTO;
import Job.AI.global.BaseResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/jobs/recommend")
@RequiredArgsConstructor
public class JobRestController {

    private final JobService jobService;

    @PostMapping("/tasks")
    @Operation(summary = "작업 생성 API", description = "사용자가 요청을 보내면 작업을 생성한 뒤 task ID만 반환")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse( responseCode = "200", description = "OK, 성공적으로 조회되었습니다.")
    })
    public BaseResponse<JobResponseDTO.TaskCreationDTO> setTask(
            @RequestBody JobRequestDTO.TaskInfoDTO taskInfo
    ) {
        JobResponseDTO.TaskCreationDTO result = jobService.setTask(taskInfo);
        return BaseResponse.onAccepted("AI 에이전트가 채용공고 분석을 시작했습니다.", result);
    }

    @GetMapping("/tasks/{taskId}")
    @Operation(summary = "작업 상태 및 결과 조회 API", description = "발급받은 task_id를 통해 AI 추천 작업의 진행 상태(Polling)와 최종 결과를 조회합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "OK, 성공적으로 상태 및 결과가 조회되었습니다.")
    })
    public BaseResponse<List<JobResponseDTO.JobDataDTO>> getTaskStatus(
            @PathVariable("taskId") String taskId
    ) {
        JobResponseDTO.TaskStatusDTO result = jobService.getTaskStatus(taskId);
        return BaseResponse.of(result.getStatus(), result.getMessage(), result.getData());
    }
}
