/*
 * couchbox-screencast: ask KWin for a PipeWire stream of the TV screen, for couchbox-record.
 *
 * KWin streams a screen only to programs whose .desktop file lists zkde_screencast_unstable_v1
 * (X-KDE-Wayland-Interfaces), matched by the program's executable; this program's is
 * /usr/share/applications/couchbox-screencast.desktop. The protocol is Wayland's, which Python
 * doesn't speak, hence a few lines of C on libwayland-client. It records nothing itself: it asks
 * for the stream, says which PipeWire node to read, and keeps the stream open while a PipeWire
 * client (couchbox-record's GStreamer pipeline) reads it.
 *
 *   couchbox-screencast [--cursor] [--output NAME]
 *
 * Prints one line once KWin has made the stream:
 *   node=ID serial=SERIAL width=W height=H output=NAME
 * (serial 0 from a KWin older than protocol version 6), then holds the stream until its standard
 * input closes, SIGTERM or SIGINT arrives, or KWin ends it. Every stream is logged with the
 * program that asked for it (journalctl -t couchbox-screencast).
 * Exit status: 0 done, 1 usage or Wayland error, 2 not authorized (KWin didn't offer the
 * interface), 3 KWin refused or ended the stream.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/signalfd.h>
#include <syslog.h>
#include <unistd.h>
#include <wayland-client.h>

#include "zkde-screencast-unstable-v1-client-protocol.h"

#define NAME "couchbox-screencast"

struct output {
	struct wl_output *wl;
	int32_t width, height;
	char name[64];
	struct output *next;
};

static struct zkde_screencast_unstable_v1 *screencast;
static struct output *outputs;
static struct {
	uint32_t node;
	uint64_t serial;
	int created, ended;
	char error[256];
} stream;

static void output_geometry(void *data, struct wl_output *wl, int32_t x, int32_t y, int32_t pw, int32_t ph,
			    int32_t subpixel, const char *make, const char *model, int32_t transform)
{
}

static void output_mode(void *data, struct wl_output *wl, uint32_t flags, int32_t width, int32_t height, int32_t refresh)
{
	struct output *o = data;

	if (flags & WL_OUTPUT_MODE_CURRENT) {
		o->width = width;
		o->height = height;
	}
}

static void output_done(void *data, struct wl_output *wl)
{
}

static void output_scale(void *data, struct wl_output *wl, int32_t factor)
{
}

static void output_name(void *data, struct wl_output *wl, const char *name)
{
	struct output *o = data;

	snprintf(o->name, sizeof(o->name), "%s", name);
}

static void output_description(void *data, struct wl_output *wl, const char *description)
{
}

static const struct wl_output_listener output_listener = {
	.geometry = output_geometry,
	.mode = output_mode,
	.done = output_done,
	.scale = output_scale,
	.name = output_name,
	.description = output_description,
};

static void global(void *data, struct wl_registry *registry, uint32_t id, const char *interface, uint32_t version)
{
	if (strcmp(interface, zkde_screencast_unstable_v1_interface.name) == 0) {
		screencast = wl_registry_bind(registry, id, &zkde_screencast_unstable_v1_interface, version < 6 ? version : 6);
	} else if (strcmp(interface, wl_output_interface.name) == 0) {
		struct output *o = calloc(1, sizeof(*o)), **tail = &outputs;

		if (!o)
			return;
		o->wl = wl_registry_bind(registry, id, &wl_output_interface, version < 4 ? version : 4);
		wl_output_add_listener(o->wl, &output_listener, o);
		while (*tail)
			tail = &(*tail)->next;
		*tail = o;
	}
}

static void global_remove(void *data, struct wl_registry *registry, uint32_t id)
{
}

static const struct wl_registry_listener registry_listener = { .global = global, .global_remove = global_remove };

static void stream_closed(void *data, struct zkde_screencast_stream_unstable_v1 *s)
{
	stream.ended = 1;
	snprintf(stream.error, sizeof(stream.error), "KWin closed the stream");
}

static void stream_created(void *data, struct zkde_screencast_stream_unstable_v1 *s, uint32_t node)
{
	stream.node = node;
	stream.created = 1;
}

static void stream_failed(void *data, struct zkde_screencast_stream_unstable_v1 *s, const char *error)
{
	stream.ended = 1;
	snprintf(stream.error, sizeof(stream.error), "KWin refused the stream: %s", error);
}

static void stream_serial(void *data, struct zkde_screencast_stream_unstable_v1 *s, uint32_t hi, uint32_t lo)
{
	stream.serial = (uint64_t)hi << 32 | lo;
}

static const struct zkde_screencast_stream_unstable_v1_listener stream_listener = {
	.closed = stream_closed,
	.created = stream_created,
	.failed = stream_failed,
	.serial = stream_serial,
};

/* "PID (/path/to/exe)" of the program that started us, for the log */
static void parent(char *buf, size_t size)
{
	char link[64], exe[PATH_MAX];
	ssize_t n;

	snprintf(link, sizeof(link), "/proc/%d/exe", (int)getppid());
	n = readlink(link, exe, sizeof(exe) - 1);
	exe[n > 0 ? n : 0] = '\0';
	snprintf(buf, size, "%d (%s)", (int)getppid(), n > 0 ? exe : "?");
}

/* dispatch Wayland events until stdin closes, a signal arrives or the stream ends */
static int hold(struct wl_display *display, int sigfd)
{
	struct pollfd fds[3] = {
		{ .fd = wl_display_get_fd(display), .events = POLLIN },
		{ .fd = STDIN_FILENO, .events = POLLIN },
		{ .fd = sigfd, .events = POLLIN },
	};
	char buf[256];

	while (!stream.ended) {
		while (wl_display_prepare_read(display) != 0)
			wl_display_dispatch_pending(display);
		wl_display_flush(display);
		if (poll(fds, 3, -1) < 0) {
			wl_display_cancel_read(display);
			if (errno == EINTR)
				continue;
			return -1;
		}
		if (fds[0].revents & (POLLIN | POLLERR | POLLHUP)) {
			if (wl_display_read_events(display) < 0)
				return -1;
		} else {
			wl_display_cancel_read(display);
		}
		if (wl_display_dispatch_pending(display) < 0)
			return -1;
		if (fds[1].revents & (POLLIN | POLLHUP | POLLERR)) {
			ssize_t n = read(STDIN_FILENO, buf, sizeof(buf));

			if (n <= 0 && !(n < 0 && errno == EINTR))
				return 0;
		}
		if (fds[2].revents & POLLIN)
			return 0;
	}
	return 0;
}

int main(int argc, char **argv)
{
	const char *want = NULL;
	uint32_t pointer = ZKDE_SCREENCAST_UNSTABLE_V1_POINTER_HIDDEN;
	struct zkde_screencast_stream_unstable_v1 *s;
	struct wl_display *display;
	struct output *o;
	char who[PATH_MAX + 32];
	sigset_t mask;
	int sigfd, rc = 0;

	for (int i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--cursor") == 0) {
			pointer = ZKDE_SCREENCAST_UNSTABLE_V1_POINTER_EMBEDDED;
		} else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
			want = argv[++i];
		} else {
			fprintf(stderr, "usage: " NAME " [--cursor] [--output NAME]\n");
			return 1;
		}
	}
	/* signals arrive on a descriptor, beside Wayland's and stdin; a closed stdout isn't fatal */
	sigemptyset(&mask);
	sigaddset(&mask, SIGTERM);
	sigaddset(&mask, SIGINT);
	sigaddset(&mask, SIGHUP);
	sigprocmask(SIG_BLOCK, &mask, NULL);
	signal(SIGPIPE, SIG_IGN);
	sigfd = signalfd(-1, &mask, SFD_CLOEXEC);
	openlog(NAME, LOG_PID, LOG_USER);
	parent(who, sizeof(who));

	display = wl_display_connect(NULL);
	if (!display) {
		fprintf(stderr, NAME ": can't reach the Wayland display (WAYLAND_DISPLAY, XDG_RUNTIME_DIR)\n");
		return 1;
	}
	wl_registry_add_listener(wl_display_get_registry(display), &registry_listener, NULL);
	wl_display_roundtrip(display); /* the globals */
	wl_display_roundtrip(display); /* the outputs' modes and names */
	if (!screencast) {
		fprintf(stderr, NAME ": KWin doesn't offer zkde_screencast_unstable_v1 to this program "
				"(is /usr/share/applications/couchbox-screencast.desktop installed, and is this KWin?)\n");
		syslog(LOG_WARNING, "not authorized for screencasting (asked by %s)", who);
		return 2;
	}
	for (o = outputs; o; o = o->next)
		if (!want || strcmp(o->name, want) == 0)
			break;
	if (!o) {
		fprintf(stderr, NAME ": no output %s\n", want ? want : "at all");
		return 1;
	}

	s = zkde_screencast_unstable_v1_stream_output(screencast, o->wl, pointer);
	zkde_screencast_stream_unstable_v1_add_listener(s, &stream_listener, NULL);
	while (!stream.created && !stream.ended)
		if (wl_display_dispatch(display) < 0)
			break;
	if (!stream.created) {
		fprintf(stderr, NAME ": %s\n", stream.ended ? stream.error : "lost the Wayland connection");
		syslog(LOG_WARNING, "no stream of %s for %s: %s", o->name, who, stream.ended ? stream.error : "Wayland error");
		zkde_screencast_stream_unstable_v1_close(s);
		wl_display_roundtrip(display);
		return 3;
	}
	syslog(LOG_INFO, "streaming %s (%dx%d, PipeWire node %u) for %s", o->name, o->width, o->height, stream.node, who);
	printf("node=%u serial=%llu width=%d height=%d output=%s\n", stream.node, (unsigned long long)stream.serial, o->width,
	       o->height, o->name[0] ? o->name : "-");
	fflush(stdout);

	if (hold(display, sigfd) < 0) {
		fprintf(stderr, NAME ": lost the Wayland connection\n");
		rc = 1;
	} else if (stream.ended) {
		fprintf(stderr, NAME ": %s\n", stream.error);
		rc = 3;
	}
	syslog(LOG_INFO, "stream of %s ended for %s%s%s", o->name, who, stream.ended ? ": " : "", stream.ended ? stream.error : "");
	zkde_screencast_stream_unstable_v1_close(s); /* also after KWin ended it, as the protocol asks */
	wl_display_roundtrip(display);
	wl_display_disconnect(display);
	return rc;
}
