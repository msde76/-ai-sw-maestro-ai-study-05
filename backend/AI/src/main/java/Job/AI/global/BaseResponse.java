package Job.AI.global;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
@JsonPropertyOrder({"status", "message", "data"}) // JSON 출력 순서 고정
public class BaseResponse<T> {

    private final String status;
    private final String message;

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private final T data;

    // 1. 작업 생성 성공 (ACCEPTED)
    public static <T> BaseResponse<T> onAccepted(String message, T data) {
        return new BaseResponse<>("ACCEPTED", message, data);
    }

    // 2. 작업 처리 중 (PROCESSING)
    public static <T> BaseResponse<T> onProcessing(String message, T data) {
        return new BaseResponse<>("PROCESSING", message, data);
    }

    // 3. 작업 완료 (COMPLETED)
    public static <T> BaseResponse<T> onCompleted(String message, T data) {
        return new BaseResponse<>("COMPLETED", message, data);
    }

    // 4. 결과 없음 (EMPTY)
    public static <T> BaseResponse<T> onEmpty(String message) {
        return new BaseResponse<>("EMPTY", message, null);
    }

    // 5. 에러 발생 (ERROR)
    public static <T> BaseResponse<T> onError(String message) {
        return new BaseResponse<>("ERROR", message, null);
    }

    // 6. 직접 상태와 메시지를 지정하고 싶을 때 (기존 SuccessStatus Enum 등을 활용할 경우)
    public static <T> BaseResponse<T> of(String status, String message, T data) {
        return new BaseResponse<>(status, message, data);
    }
}