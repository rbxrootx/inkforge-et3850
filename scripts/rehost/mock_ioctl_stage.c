/* Offline QEMU rehost only: minimal synthetic EPIDC controller reply. */
typedef unsigned int u32;
extern int mprotect(void *address, unsigned long length, int protection);
extern long write(int fd, const void *buffer, unsigned long count);
extern long syscall(long number, ...);
extern int snprintf(char *buffer, unsigned int size, const char *format, ...);
int ioctl(int fd, unsigned long request, void *arg);
static unsigned char channel_by_fd[64];
static unsigned int channel_info_stage;
static const unsigned char channel_info_reply[] =
    "UpChannelNum:01\x1b\r\nDownChannelNum:01\x1b\r\n";
static const unsigned char main_version_reply[] =
    "Status:00000000\x1b\r\nMainVersion:1.0.0\x1b\r\n";
static const unsigned char main_year_reply[] =
    "Status:00000000\x1b\r\nMainYearInfo:2025\x1b\r\n";
#ifdef MOCK_GET_REQUEST_ID
/* Deliberately invented response for offline body-path control-flow research. */
static const unsigned char get_request_id_reply[] =
    "HR:200\x1b\r\nRequestID:0\x1b\r\nChID:1\x1b\r\n";
#endif
static const unsigned char *active_reply = channel_info_reply;
static u32 active_reply_length = sizeof(channel_info_reply) - 1;

static int contains_bytes(const unsigned char *input, u32 size, const char *needle, u32 needle_size) {
    for (u32 i = 0; i + needle_size <= size; ++i) {
        u32 j = 0;
        while (j < needle_size && input[i + j] == (unsigned char)needle[j]) ++j;
        if (j == needle_size) return 1;
    }
    return 0;
}

static void trace_request(const char *name, int fd, u32 *packet, int words) {
    static unsigned int lines = 0;
    char line[240];
    int length;
    if (lines++ > 120) return;
    length = snprintf(line, sizeof(line), "MOCK %s fd=%d arg=%08x,%08x,%08x,%08x,%08x,%08x\n",
                      name, fd, packet[0], packet[1], packet[2],
                      words > 3 ? packet[3] : 0, words > 4 ? packet[4] : 0,
                      words > 5 ? packet[5] : 0);
    if (length > 0 && length < (int)sizeof(line)) write(2, line, (unsigned long)length);
}

static void trace_send_bytes(int fd, u32 *packet) {
    static unsigned int lines = 0;
    char line[320];
    int used;
    unsigned int count;
    const unsigned char *source;
    if (fd < 0 || fd >= 64 || channel_by_fd[fd] != 10 || packet[1] > 256 || lines++ >= 24) return;
    source = (const unsigned char *)packet[0];
    count = packet[1] < 128 ? packet[1] : 128;
    used = snprintf(line, sizeof(line), "MOCK SENDHEX fd=%d len=%u data=", fd, packet[1]);
    for (unsigned int i = 0; i < count && used > 0 && used + 4 < (int)sizeof(line); ++i)
        used += snprintf(line + used, sizeof(line) - used, "%02x", source[i]);
    if (used > 0 && used + 2 < (int)sizeof(line)) {
        line[used++] = '\n';
        write(2, line, (unsigned long)used);
    }
}

__attribute__((constructor)) static void install_override(void) {
    static const char loaded[] = "stage mock constructor\n";
    write(2, loaded, sizeof(loaded) - 1);
    if (mprotect((void *)0x00691000UL, 4096, 3) == 0) {
        static const char ready[] = "stage mock GOT patch\n";
        write(2, ready, sizeof(ready) - 1);
        *(volatile void **)0x00691510UL = (void *)&ioctl;
    }
}

int ioctl(int fd, unsigned long request, void *arg) {
    u32 *packet = (u32 *)arg;
    if (request == 0x400cfe00UL) {
        trace_request("OPEN", fd, packet, 3);
        if (fd >= 0 && fd < 64) channel_by_fd[fd] = (unsigned char)packet[0];
        return 0;
    }
    if (request == 0xc018fe02UL) {
        trace_request("SEND", fd, packet, 6);
        trace_send_bytes(fd, packet);
        if (fd >= 0 && fd < 64 && channel_by_fd[fd] == 10 && 8 < packet[1] && packet[1] < 256) {
            const unsigned char *sent = (const unsigned char *)packet[0];
            active_reply = channel_info_reply;
            active_reply_length = sizeof(channel_info_reply) - 1;
            if (contains_bytes(sent, packet[1], "GetMainVersion", 14)) {
                active_reply = main_version_reply;
                active_reply_length = sizeof(main_version_reply) - 1;
            } else if (contains_bytes(sent, packet[1], "GetMainYearInfo", 15)) {
                active_reply = main_year_reply;
                active_reply_length = sizeof(main_year_reply) - 1;
#ifdef MOCK_GET_REQUEST_ID
            } else if (contains_bytes(sent, packet[1], "GetRequestID", 12)) {
                active_reply = get_request_id_reply;
                active_reply_length = sizeof(get_request_id_reply) - 1;
#endif
            }
            channel_info_stage = 1;
        }
        packet[2] = packet[1]; /* acknowledge all sent bytes */
        return 0;
    }
    if (request == 0xc018fe03UL) {
        trace_request("RECV", fd, packet, 6);
        static u32 receive_count = 0;
        static const unsigned char device_id[] = "MFG:EPSON;MDL:ET-3850;\f";
        static const unsigned char device_type[] = {0, 0, 0, 0, 0, 0, 0};
        static const unsigned char event_header[] = {0, 0, 0, 0, 0, 0, 0, 0};
        if (fd >= 0 && fd < 64 && channel_by_fd[fd] >= 10) {
            unsigned char *destination = (unsigned char *)packet[0];
            if (channel_by_fd[fd] == 10 && channel_info_stage == 1 && packet[1] >= 8) {
                u32 n = active_reply_length;
                destination[0] = (unsigned char)(n >> 8);
                destination[1] = (unsigned char)n;
                for (u32 i = 2; i < 8; ++i) destination[i] = 0;
                packet[2] = 8;
                packet[3] = 0;
                packet[5] = 0;
                channel_info_stage = 2;
                return 0;
            }
            if (channel_by_fd[fd] == 10 && channel_info_stage == 2 && packet[1] >= active_reply_length) {
                for (u32 i = 0; i < active_reply_length; ++i)
                    destination[i] = active_reply[i];
                packet[2] = active_reply_length;
                packet[3] = 1; /* end of D4 message */
                packet[5] = 0; /* ioctl success */
                channel_info_stage = 3;
                return 0;
            }
            struct { long seconds; long nanoseconds; } delay = {0, 20000000};
            syscall(162, &delay, 0); /* slow an otherwise hot synthetic event loop */
            if (packet[1] < sizeof(event_header)) return -1;
            for (u32 i = 0; i < sizeof(event_header); ++i) destination[i] = event_header[i];
            packet[2] = sizeof(event_header);
            packet[3] = 1;
            packet[5] = 0;
            return 0;
        }
        const unsigned char *payload = receive_count++ == 0 ? device_id : device_type;
        u32 payload_length = payload == device_id ? sizeof(device_id) - 1 : sizeof(device_type);
        unsigned char *destination = (unsigned char *)packet[0];
        if (packet[1] < payload_length + 5) return -1;
        destination[0] = (unsigned char)payload_length;
        destination[1] = (unsigned char)(payload_length >> 8);
        destination[2] = 0;
        destination[3] = 0;
        destination[4] = 0;
        for (u32 i = 0; i < payload_length; ++i) destination[5 + i] = payload[i];
        packet[2] = payload_length + 5; /* bytes received */
        packet[3] = 0; /* receiver status */
        packet[5] = 0; /* ioctl result */
        return 0;
    }
    /* Acknowledge writes without changing the WSL host's network configuration. */
    if (request == 0x8924UL || request == 0x8916UL ||
        request == 0x891aUL || request == 0x891cUL ||
        request == 0x890bUL || request == 0x400cfe01UL ||
        request == 0x4004fe0bUL) return 0;
    /* Only read-only interface and terminal queries reach the host kernel. */
    if (request == 0x8912UL || request == 0x8913UL ||
        request == 0x8915UL || request == 0x8919UL ||
        request == 0x891bUL || request == 0x8927UL ||
        request == 0x8933UL || request == 0x5401UL)
        return (int)syscall(54, fd, request, arg); /* ARM Linux __NR_ioctl */
    return -1;
}
