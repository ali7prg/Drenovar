"""Quaternion / vector helpers (x, y, z, w order, as glTF)."""
import numpy as np

F = np.float64


def q_identity():
    return np.array([0.0, 0.0, 0.0, 1.0])


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz])


def q_conj(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])


def q_axis(axis, angle):
    axis = np.asarray(axis, F)
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(angle) < 1e-12:
        return q_identity()
    s = np.sin(angle * 0.5) / n
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(angle * 0.5)])


def q_euler(pitch=0.0, yaw=0.0, roll=0.0):
    """Creature frame: pitch about +Z (side axis; positive lifts the +X nose), yaw about +Y, roll about +X."""
    return q_mul(q_axis((0, 1, 0), yaw), q_mul(q_axis((0, 0, 1), pitch), q_axis((1, 0, 0), roll)))


def q_rotate(q, v):
    u = q[:3]
    s = q[3]
    v = np.asarray(v, F)
    return 2.0 * np.dot(u, v) * u + (s * s - np.dot(u, u)) * v + 2.0 * s * np.cross(u, v)


def q_normalize(q):
    return q / np.linalg.norm(q)


def q_slerp(a, b, t):
    d = np.dot(a, b)
    if d < 0:
        b = -b
        d = -d
    if d > 0.9995:
        return q_normalize(a + t * (b - a))
    th = np.arccos(d)
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


def q_between(u, v):
    """Shortest-arc rotation taking direction u to direction v."""
    u = np.asarray(u, F) / np.linalg.norm(u)
    v = np.asarray(v, F) / np.linalg.norm(v)
    d = np.dot(u, v)
    if d < -0.999999:
        axis = np.cross(u, (1, 0, 0))
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(u, (0, 1, 0))
        return q_axis(axis, np.pi)
    c = np.cross(u, v)
    q = np.array([c[0], c[1], c[2], 1.0 + d])
    return q_normalize(q)


def q_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def q_angle(q):
    return 2.0 * np.arccos(np.clip(abs(q[3]), 0, 1))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)
