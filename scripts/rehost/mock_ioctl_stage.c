/* Offline QEMU rehost only: minimal synthetic EPIDC controller reply. */
typedef unsigned int u32;
extern int mprotect(void *address, unsigned long length, int protection);
extern long write(int fd, const void *buffer, unsigned long count);
extern long syscall(long number, ...);
int ioctl(int fd, unsigned long request, void *arg);

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
    if (request == 0x400cfe00UL) return 0;
    if (request == 0xc018fe02UL) {
        packet[2] = packet[1]; /* acknowledge all sent bytes */
        return 0;
    }
    if (request == 0xc018fe03UL) {
        static u32 receive_count = 0;
        static const unsigned char device_id[] = "MFG:EPSON;MDL:ET-3850;\f";
        static const unsigned char device_type[] = {0, 0, 0, 0, 0, 0, 0};
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
