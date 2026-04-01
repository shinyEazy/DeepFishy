export type Mode = "deep" | "normal"

export type SessionSummary = {
  id: string
  title: string
  preview: string
  time: string
  status: string
  mode: Mode
}

export type TranscriptMessage = {
  role: "user" | "assistant"
  mode: Mode
  label: string
  title: string
  body: string
  meta: string
  bullets?: readonly string[]
  references?: readonly string[]
}

export type SessionContent = {
  id: string
  title: string
  mode: Mode
  subtitle: string
  inputPlaceholder: string
  quickActions: readonly string[]
  transcript: readonly TranscriptMessage[]
}

export const modeOptions = [
  {
    id: "deep",
    label: "Nghiên cứu sâu",
    description: "Tổng hợp dài hơn, có nguồn.",
  },
  {
    id: "normal",
    label: "Hỏi nhanh",
    description: "Trả lời nhanh và gọn.",
  },
] as const

export const sessionGroups: ReadonlyArray<{
  label: string
  sessions: readonly SessionSummary[]
}> = [
  {
    label: "Gần đây",
    sessions: [
      {
        id: "chao-hoi-ngan-gon",
        title: "Chào hỏi ngắn gọn",
        preview: "Hỏi đáp nhanh.",
        time: "Hôm nay",
        status: "Hỏi nhanh",
        mode: "normal",
      },
      {
        id: "ke-hoach-ra-mat-viet-nam",
        title: "Kế hoạch ra mắt Việt Nam",
        preview: "Thị trường, rủi ro, 90 ngày.",
        time: "8:42",
        status: "Nghiên cứu sâu",
        mode: "deep",
      },
      {
        id: "sua-copy-onboarding",
        title: "Sửa copy onboarding",
        preview: "Thông điệp ngắn hơn.",
        time: "7:15",
        status: "Hỏi nhanh",
        mode: "normal",
      },
    ],
  },
]

export const defaultSessionId = sessionGroups[0]?.sessions[0]?.id ?? ""

const sessionContent: Record<string, SessionContent> = {
  "chao-hoi-ngan-gon": {
    id: "chao-hoi-ngan-gon",
    title: "Notebook chưa đặt tên",
    mode: "normal",
    subtitle: "Trả lời nhanh cho câu hỏi hằng ngày.",
    inputPlaceholder: "Hãy hỏi bất kỳ điều gì!",
    quickActions: ["Tóm tắt", "Giải thích", "Viết lại"],
    transcript: [
      {
        role: "user",
        mode: "normal",
        label: "Bạn",
        title: "Chào hỏi ngắn gọn",
        body: "Giúp tôi viết một lời chào ngắn gọn cho người dùng mới.",
        meta: "Hôm nay, 09:10",
        references: ["Hỏi nhanh"],
      },
      {
        role: "assistant",
        mode: "normal",
        label: "DeepFishy",
        title: "Gợi ý",
        body: "Xin chào! Bạn có thể bắt đầu bằng cách đặt câu hỏi đầu tiên, và chúng tôi sẽ giúp bạn tìm câu trả lời nhanh hơn.",
        meta: "Sẵn sàng để dùng",
        bullets: ["Ngắn gọn.", "Thân thiện.", "Dễ đưa vào UI."],
        references: ["Copy sẵn sàng"],
      },
    ],
  },
  "ke-hoach-ra-mat-viet-nam": {
    id: "ke-hoach-ra-mat-viet-nam",
    title: "Kế hoạch ra mắt Việt Nam",
    mode: "deep",
    subtitle: "Tổng hợp thị trường, rủi ro và kế hoạch 90 ngày.",
    inputPlaceholder: "Soạn brief ra mắt thị trường Việt Nam.",
    quickActions: ["90 ngày", "Rủi ro", "Tóm tắt lãnh đạo"],
    transcript: [
      {
        role: "user",
        mode: "deep",
        label: "Bạn",
        title: "Cần một brief ra mắt",
        body: "Tôi cần tổng quan thị trường, rủi ro vận hành và một kế hoạch 90 ngày. Đánh dấu phần nào cần con người phê duyệt.",
        meta: "08:42",
        references: ["Nghiên cứu sâu"],
      },
      {
        role: "assistant",
        mode: "deep",
        label: "DeepFishy",
        title: "Đã chia thành 3 nhóm",
        body: "Tôi tách vấn đề thành nhu cầu thị trường, vận hành và tuân thủ. Hai điểm cần xem tay sớm nhất là thanh toán và hỗ trợ khách hàng.",
        meta: "12 nguồn • 4 câu hỏi mở",
        bullets: [
          "Nhu cầu có dấu hiệu tốt.",
          "Thanh toán và support cần xem kỹ.",
          "Nên bắt đầu bằng pilot nhỏ.",
        ],
        references: ["Nguồn bật", "Tóm tắt lãnh đạo"],
      },
      {
        role: "user",
        mode: "normal",
        label: "Bạn",
        title: "Cho tôi bản ngắn hơn",
        body: "Tôi cần một bản rất gọn để gửi cho leadership.",
        meta: "08:49",
        references: ["Hỏi nhanh"],
      },
      {
        role: "assistant",
        mode: "normal",
        label: "DeepFishy",
        title: "Bản tóm tắt",
        body: "Việt Nam là thị trường tiềm năng, nhưng nên ra mắt theo mô hình pilot. Rủi ro lớn nhất hiện tại nằm ở thanh toán, support và tuân thủ.",
        meta: "Sẵn sàng copy",
        bullets: [
          "Ra mắt pilot trước.",
          "Kiểm tra thanh toán và support.",
          "Mở rộng sau đợt đầu.",
        ],
        references: ["Copy sẵn sàng"],
      },
    ],
  },
  "sua-copy-onboarding": {
    id: "sua-copy-onboarding",
    title: "Sửa copy onboarding",
    mode: "normal",
    subtitle: "Điều chỉnh thông điệp mở đầu cho rõ hơn.",
    inputPlaceholder: "Viết lại thông điệp onboarding ngắn hơn.",
    quickActions: ["Ngắn hơn", "Thân thiện hơn", "Mạnh mẽ hơn"],
    transcript: [
      {
        role: "user",
        mode: "normal",
        label: "Bạn",
        title: "Viết lại thông điệp",
        body: "Hãy viết lại thông điệp onboarding sao cho gọn, rõ và tự tin hơn.",
        meta: "07:15",
        references: ["Hỏi nhanh"],
      },
      {
        role: "assistant",
        mode: "normal",
        label: "DeepFishy",
        title: "Bản mới",
        body: "Bắt đầu nhanh hơn. Kết nối dữ liệu, đặt câu hỏi đầu tiên, và nhận câu trả lời trong vài giây.",
        meta: "Đã xong",
        bullets: ["Rõ hơn.", "Ngắn hơn.", "Tập trung hành động."],
        references: ["Copy mới"],
      },
    ],
  },
}

export function getSessionContent(sessionId?: string) {
  if (sessionId && sessionContent[sessionId]) {
    return sessionContent[sessionId]
  }

  return sessionContent[defaultSessionId]
}
