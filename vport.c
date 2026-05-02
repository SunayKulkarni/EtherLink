#include "tap_utils.h"
#include "sys_utils.h"
#include <stdbool.h>
#include <assert.h>
#include <stdint.h>
#include <arpa/inet.h>
#include <net/ethernet.h>
#include <netdb.h>
#include <pthread.h>

/**
 * VPort Instance
 */
struct vport_t
{
  int tapfd;                       // TAP device file descriptor, connected to linux kernel network stack
  int vport_sockfd;                // client socket, for communicating with VSwitch
  struct sockaddr_in vswitch_addr; // VSwitch address
};

void vport_init(struct vport_t *vport, const char *server_ip_str, int server_port);
void *forward_ether_data_to_vswitch(void *raw_vport);
void *forward_ether_data_to_tap(void *raw_vport);

int main(int argc, char const *argv[])
{
  // parse arguments
  if (argc != 3)
  {
    ERROR_PRINT_THEN_EXIT("Usage: vport {server_ip} {server_port}\n");
  }
  const char *server_ip_str = argv[1];
  int server_port = atoi(argv[2]);

  // vport init
  struct vport_t vport;
  vport_init(&vport, server_ip_str, server_port);

  // up forwarder
  pthread_t up_forwarder;
  if (pthread_create(&up_forwarder, NULL, forward_ether_data_to_vswitch, &vport) != 0)
  {
    ERROR_PRINT_THEN_EXIT("fail to pthread_create: %s\n", strerror(errno));
  }

  // down forwarder
  pthread_t down_forwarder;
  if (pthread_create(&down_forwarder, NULL, forward_ether_data_to_tap, &vport) != 0)
  {
    ERROR_PRINT_THEN_EXIT("fail to pthread_create: %s\n", strerror(errno));
  }

  // wait for up forwarder & down forwarder
  if (pthread_join(up_forwarder, NULL) != 0 || pthread_join(down_forwarder, NULL) != 0)
  {
    ERROR_PRINT_THEN_EXIT("fail to pthread_join: %s\n", strerror(errno));
  }

  return 0;
}

/**
 * init VPort instance: create TAP device and client socket
 */
void vport_init(struct vport_t *vport, const char *server_ip_str, int server_port)
{
  // alloc tap device
  char ifname[IFNAMSIZ] = "tapyuan";
  int tapfd = tap_alloc(ifname);
  if (tapfd < 0)
  {
    ERROR_PRINT_THEN_EXIT("fail to tap_alloc: %s\n", strerror(errno));
  }

  // create socket
  int vport_sockfd = socket(AF_INET, SOCK_DGRAM, 0);
  if (vport_sockfd < 0)
  {
    ERROR_PRINT_THEN_EXIT("fail to socket: %s\n", strerror(errno));
  }

  // setup vswitch info
  struct sockaddr_in vswitch_addr;
  memset(&vswitch_addr, 0, sizeof(vswitch_addr));
  vswitch_addr.sin_family = AF_INET;
  vswitch_addr.sin_port = htons(server_port);
  
  // Try inet_pton first (for IP addresses)
  int pton_result = inet_pton(AF_INET, server_ip_str, &vswitch_addr.sin_addr);
  if (pton_result <= 0)
  {
    // If inet_pton fails, try gethostbyname for hostnames like "localhost"
    struct hostent *host = gethostbyname(server_ip_str);
    if (host == NULL)
    {
      ERROR_PRINT_THEN_EXIT("fail to resolve address: %s\n", server_ip_str);
    }
    memcpy(&vswitch_addr.sin_addr, host->h_addr_list[0], host->h_length);
  }

  vport->tapfd = tapfd;
  vport->vport_sockfd = vport_sockfd;
  vport->vswitch_addr = vswitch_addr;

  printf("[VPort] TAP device name: %s, VSwitch: %s:%d\n", ifname, server_ip_str, server_port);
}

/**
 * Validate Ethernet frame: check size and header validity
 * Returns 1 if valid, 0 if invalid
 */
static int validate_ethernet_frame(const char *data, int datasz)
{
  // Minimum: Ethernet header (14 bytes) + payload
  static const int ETHERNET_FRAME_MIN = 64;
  static const int ETHERNET_FRAME_MAX = 1518;
  static const int ETHERNET_HEADER_SIZE = 14;

  // Check size bounds
  if (datasz < ETHERNET_HEADER_SIZE)
  {
    fprintf(stderr, "[VPort] INVALID: Frame too small (%d < %d)\n", datasz, ETHERNET_HEADER_SIZE);
    return 0;
  }

  /*if (datasz < ETHERNET_FRAME_MIN)
  {
    fprintf(stderr, "[VPort] INVALID: Frame below minimum (%d < %d)\n", datasz, ETHERNET_FRAME_MIN);
    return 0;
  }
 */


  if (datasz > ETHERNET_FRAME_MAX)
  {
    fprintf(stderr, "[VPort] INVALID: Frame exceeds maximum (%d > %d)\n", datasz, ETHERNET_FRAME_MAX);
    return 0;
  }

  // Validate Ethernet header
  const struct ether_header *hdr = (const struct ether_header *)data;

  // Check that we can safely read the header
  if ((uintptr_t)hdr + sizeof(struct ether_header) > (uintptr_t)data + datasz)
  {
    fprintf(stderr, "[VPort] INVALID: Insufficient buffer for Ethernet header\n");
    return 0;
  }

  return 1;
}

/**
 * Forward ethernet frame from TAP device to VSwitch
 */
void *forward_ether_data_to_vswitch(void *raw_vport)
{
  struct vport_t *vport = (struct vport_t *)raw_vport;
  char ether_data[ETHER_MAX_LEN];
  while (true)
  {
    // read ethernet from tap device
    int ether_datasz = read(vport->tapfd, ether_data, sizeof(ether_data));
    
    if (ether_datasz < 0)
    {
      fprintf(stderr, "[VPort] ERROR: read from TAP failed: %s\n", strerror(errno));
      continue;
    }

    if (ether_datasz == 0)
    {
      fprintf(stderr, "[VPort] WARNING: read from TAP returned 0 bytes\n");
      continue;
    }

    // Validate frame before processing
    if (!validate_ethernet_frame(ether_data, ether_datasz))
    {
      continue;  // Skip invalid frame
    }

    const struct ether_header *hdr = (const struct ether_header *)ether_data;

    // forward ethernet frame to VSwitch
    ssize_t sendsz = sendto(vport->vport_sockfd, ether_data, ether_datasz, 0, 
                            (struct sockaddr *)&vport->vswitch_addr, sizeof(vport->vswitch_addr));
    if (sendsz < 0)
    {
      fprintf(stderr, "[VPort] ERROR: sendto failed: %s\n", strerror(errno));
      continue;
    }

    if (sendsz != ether_datasz)
    {
      fprintf(stderr, "[VPort] WARNING: sendto size mismatch: ether_datasz=%d, sendsz=%zd\n", 
              ether_datasz, sendsz);
      continue;
    }

    printf("[VPort] Sent to VSwitch:"
           " dhost<%02x:%02x:%02x:%02x:%02x:%02x>"
           " shost<%02x:%02x:%02x:%02x:%02x:%02x>"
           " type<%04x>"
           " datasz=<%d>\n",
           hdr->ether_dhost[0], hdr->ether_dhost[1], hdr->ether_dhost[2], hdr->ether_dhost[3], hdr->ether_dhost[4], hdr->ether_dhost[5],
           hdr->ether_shost[0], hdr->ether_shost[1], hdr->ether_shost[2], hdr->ether_shost[3], hdr->ether_shost[4], hdr->ether_shost[5],
           ntohs(hdr->ether_type),
           ether_datasz);
  }
}

/**
 * Forward ethernet frame from VSwitch to TAP device
 */
void *forward_ether_data_to_tap(void *raw_vport)
{
  struct vport_t *vport = (struct vport_t *)raw_vport;
  char ether_data[ETHER_MAX_LEN];
  socklen_t vswitch_addr_len;
  
  while (true)
  {
    // read ethernet frame from VSwitch
    vswitch_addr_len = sizeof(vport->vswitch_addr);
    int ether_datasz = recvfrom(vport->vport_sockfd, ether_data, sizeof(ether_data), 0,
                                (struct sockaddr *)&vport->vswitch_addr, &vswitch_addr_len);
    
    if (ether_datasz < 0)
    {
      fprintf(stderr, "[VPort] ERROR: recvfrom failed: %s\n", strerror(errno));
      continue;
    }

    if (ether_datasz == 0)
    {
      fprintf(stderr, "[VPort] WARNING: recvfrom returned 0 bytes\n");
      continue;
    }

    // Validate frame before writing to TAP
    if (!validate_ethernet_frame(ether_data, ether_datasz))
    {
      continue;  // Skip invalid frame
    }

    const struct ether_header *hdr = (const struct ether_header *)ether_data;

    // forward ethernet frame to TAP device (Linux network stack)
    ssize_t sendsz = write(vport->tapfd, ether_data, ether_datasz);
    if (sendsz < 0)
    {
      fprintf(stderr, "[VPort] ERROR: write to TAP failed: %s\n", strerror(errno));
      continue;
    }

    if (sendsz != ether_datasz)
    {
      fprintf(stderr, "[VPort] WARNING: write size mismatch: ether_datasz=%d, sendsz=%zd\n", 
              ether_datasz, sendsz);
      continue;
    }

    printf("[VPort] Forward to TAP device:"
           " dhost<%02x:%02x:%02x:%02x:%02x:%02x>"
           " shost<%02x:%02x:%02x:%02x:%02x:%02x>"
           " type<%04x>"
           " datasz=<%d>\n",
           hdr->ether_dhost[0], hdr->ether_dhost[1], hdr->ether_dhost[2], hdr->ether_dhost[3], hdr->ether_dhost[4], hdr->ether_dhost[5],
           hdr->ether_shost[0], hdr->ether_shost[1], hdr->ether_shost[2], hdr->ether_shost[3], hdr->ether_shost[4], hdr->ether_shost[5],
           ntohs(hdr->ether_type),
           ether_datasz);
  }
}