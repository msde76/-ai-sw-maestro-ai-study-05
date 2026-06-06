package Job.AI.domain.jobs.application;

import Job.AI.domain.jobs.dto.JobResponseDTO;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class JobAsyncWorkerTest {

    private final JobAsyncWorker worker = new JobAsyncWorker(null, new ObjectMapper());

    @Test
    void normalizeRecommendationsFiltersByMinimumScoreAndSortsDescending() throws Exception {
        List<JobResponseDTO.JobDataDTO> input = List.of(
                job("low", 0.3),
                job("best", 0.9),
                job("middle", 0.78)
        );

        List<JobResponseDTO.JobDataDTO> result = normalizeRecommendations(input);

        assertThat(result)
                .extracting(JobResponseDTO.JobDataDTO::getJobId)
                .containsExactly("best", "middle");
    }

    @Test
    void normalizeRecommendationsIncludesThresholdAndExcludesBelowThresholdAndNullScore() throws Exception {
        List<JobResponseDTO.JobDataDTO> input = List.of(
                job("threshold", 0.7),
                job("below", 0.69),
                job("no-score", null)
        );

        List<JobResponseDTO.JobDataDTO> result = normalizeRecommendations(input);

        assertThat(result)
                .extracting(JobResponseDTO.JobDataDTO::getJobId)
                .containsExactly("threshold");
    }

    @Test
    void normalizeRecommendationsReturnsEmptyListForNullInput() throws Exception {
        List<JobResponseDTO.JobDataDTO> result = normalizeRecommendations(null);

        assertThat(result).isEmpty();
    }

    @Test
    void createCompletionStatusReturnsEmptyWhenNoRecommendationsRemain() throws Exception {
        JobResponseDTO.TaskStatusDTO status = createCompletionStatus(List.of());

        assertThat(status.getStatus()).isEqualTo("EMPTY");
        assertThat(status.getData()).isEmpty();
        assertThat(status.getMessage()).contains("적합도 0.7 이상");
    }

    @Test
    void createCompletionStatusReturnsCompletedWithNormalizedData() throws Exception {
        List<JobResponseDTO.JobDataDTO> recommendations = List.of(job("recommended", 0.9));

        JobResponseDTO.TaskStatusDTO status = createCompletionStatus(recommendations);

        assertThat(status.getStatus()).isEqualTo("COMPLETED");
        assertThat(status.getData()).containsExactlyElementsOf(recommendations);
        assertThat(status.getMessage()).contains("원문 링크");
    }

    @SuppressWarnings("unchecked")
    private List<JobResponseDTO.JobDataDTO> normalizeRecommendations(List<JobResponseDTO.JobDataDTO> input) throws Exception {
        Method method = JobAsyncWorker.class.getDeclaredMethod("normalizeRecommendations", List.class);
        method.setAccessible(true);
        return (List<JobResponseDTO.JobDataDTO>) method.invoke(worker, (Object) input);
    }

    private JobResponseDTO.TaskStatusDTO createCompletionStatus(List<JobResponseDTO.JobDataDTO> input) throws Exception {
        Method method = JobAsyncWorker.class.getDeclaredMethod("createCompletionStatus", List.class);
        method.setAccessible(true);
        return (JobResponseDTO.TaskStatusDTO) method.invoke(worker, (Object) input);
    }

    private JobResponseDTO.JobDataDTO job(String jobId, Double suitabilityScore) {
        return JobResponseDTO.JobDataDTO.builder()
                .jobId(jobId)
                .companyName("company-" + jobId)
                .jobTitle("title-" + jobId)
                .suitabilityScore(suitabilityScore)
                .originalLink("https://example.com/jobs/" + jobId)
                .analysis(JobResponseDTO.AnalysisDTO.builder()
                        .matchReason("match")
                        .missingPoints("missing")
                        .checkpointGuide("guide")
                        .build())
                .build();
    }
}
