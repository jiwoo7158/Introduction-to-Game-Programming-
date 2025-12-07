import math
import pygame

# =========================
# Math / Geometry Utilities
# =========================

class Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def __add__(self, other): # 벡터의 덧셈
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other): # 벡터의 뺄셈
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar): # 벡터의 곱셈
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def dot(self, other): # 내적 계산
        return self.x * other.x + self.y * other.y

    def cross(self, other): # 외적 계산(2D라서 스칼라)
        return self.x * other.y - self.y * other.x

    def length(self): # 벡터의 크기 계산
        return math.hypot(self.x, self.y)

    def normalized(self): # 벡터 정규화
        l = self.length()
        if l == 0:
            return Vec2(0, 0)
        return Vec2(self.x / l, self.y / l)

    def tuple(self): # 튜플 변환
        return (self.x, self.y)

    def angle(self): # 각도 계산
        return math.atan2(self.y, self.x)

    @staticmethod
    def from_angle(theta): #각도를 입력받아 단위 방향 벡터 생성
        return Vec2(math.cos(theta), math.sin(theta))


# =========================
# Geometry Primitives
# =========================

class Segment:
    # p1과 p2 사이의 선분
    __slots__ = ("p1", "p2")

    def __init__(self, p1, p2):
        self.p1 = p1  # 벡터 1
        self.p2 = p2  # 벡터 2

    def points(self):
        return self.p1, self.p2


class Wall:
    # velocity : 벽의 선형 이동 속도
    # angular_apeed : 벽의 각속도(라디안/초)
    # rotation_center : 회전의 기준점
    # self.angle : 프레임마다 누적되는 회전값
    def __init__(self, p1, p2, dynamic=False, rotation_center=None, angular_speed=0.0, velocity=None):
        self.base_p1 = Vec2(p1.x, p1.y)
        self.base_p2 = Vec2(p2.x, p2.y)
        self.segment = Segment(Vec2(p1.x, p1.y), Vec2(p2.x, p2.y))

        #Dynamics
        self.dynamic = dynamic
        self.rotation_center = rotation_center  # 벡터2 혹은 없음
        self.angular_speed = angular_speed     # radians per second
        self.velocity = velocity or Vec2(0, 0) # 속도
        self.angle = 0.0

    def update(self, dt): # Wall.update
        if not self.dynamic:
            return

        # 회전
        if self.rotation_center is not None and self.angular_speed != 0.0:
            self.angle += self.angular_speed * dt
            # 회전 중심점을 기준으로 베이스 포인트를 회전시킨다
            self.segment.p1 = rotate_around(self.base_p1, self.rotation_center, self.angle)
            self.segment.p2 = rotate_around(self.base_p2, self.rotation_center, self.angle)
        # 평행 이동
        if self.velocity.x != 0 or self.velocity.y != 0:
            dp = self.velocity * dt
            self.segment.p1 = self.segment.p1 + dp
            self.segment.p2 = self.segment.p2 + dp

    def get_segment(self):
        return self.segment


def rotate_around(point, center, angle):
    # 각도 중심으로 포인트 회전
    translated = point - center
    c = math.cos(angle)
    s = math.sin(angle)
    rotated = Vec2(
        translated.x * c - translated.y * s,
        translated.x * s + translated.y * c
    )
    return center + rotated


# =========================
# Visibility Engine
# =========================

class VisibilityEngine:
    def __init__(self, walls):
        # walls: list[Wall]
        self.walls = walls

    def compute_visibility_polygon(self, origin, facing_angle, fov_angle, full_360=False):
        # origin : 벡터 2 (플레이어 위치)
        # facing_angle : 방향 라디안
        # fov_angle : 시야각 라디안 (360도 모드 = False일 때만 사용)
        # 반환 (points, hit_walls)
        # points : list[Vec2], 가시 폴리곤
        # hit_walls : 모든 ray에 대하여 hit된 벽들 모음
        eps = 1e-3
        angles = []

        # 모든 벽 끝점 기준으로 후보 각도 생성
        for wall in self.walls:
            seg = wall.get_segment()
            for p in (seg.p1, seg.p2):
                rel = p - origin
                angle = math.atan2(rel.y, rel.x)
                angles.extend([angle - eps, angle, angle + eps])

        # 360도 모드면 전체 각도 샘플, 아니면 FOV 주변 추가 샘플
        if full_360:
            steps = 64
            for i in range(steps):
                a = -math.pi + 2 * math.pi * i / steps
                angles.append(a)
        else:
            steps = 32
            half = fov_angle / 2.0
            for i in range(steps + 1):
                t = -half + fov_angle * i / steps
                angles.append(facing_angle + t)

        # 정규화 + FOV 필터링
        unique_angles = []
        seen = set()
        for a in angles:
            # Normalize to [-pi, pi]
            a = math.atan2(math.sin(a), math.cos(a))
            key = round(a, 4)
            if key in seen:
                continue
            seen.add(key)
            if not full_360:
                # 시야각(FOV)을 facing angle 주변으로 제한한다
                diff = angle_diff(a, facing_angle)
                if abs(diff) > fov_angle / 2.0:
                    continue
            unique_angles.append(a)

        unique_angles.sort()

        points = []
        hit_walls = set()

        for a in unique_angles:
            hit_point, hit_wall = self.cast_ray(origin, a)
            if hit_point is not None:
                points.append((a, hit_point))
                if hit_wall is not None:
                    hit_walls.add(hit_wall)

        if full_360:
            # 360도 모드는 그냥 절대각도로 정렬
            unique_angles.sort()
            ordered_angles = unique_angles
        else:
            # FOV 모드: 바라보는 각도 기준의 상대각(diff)으로 정렬
            angle_pairs = []
            for a in unique_angles:
                diff = angle_diff(a, facing_angle)   # [-pi, pi] 범위의 상대각
                angle_pairs.append((diff, a))

            angle_pairs.sort(key=lambda x: x[0])      # diff 기준으로 정렬
            ordered_angles = [a for diff, a in angle_pairs]

        points = []
        hit_walls = set()

        for a in ordered_angles:
            hit_point, hit_wall = self.cast_ray(origin, a)
            if hit_point is not None:
                points.append((a, hit_point))
                if hit_wall is not None:
                    hit_walls.add(hit_wall)

        # Sort by angle and return positions only
        #points.sort(key=lambda ap: ap[0])
        poly_points = [p for _, p in points]

        return poly_points, hit_walls

    def cast_ray(self, origin, angle, max_dist=1000.0):
        """
        Cast a ray from origin in given angle.
        Returns (closest_point, wall)
        """
        direction = Vec2.from_angle(angle)
        closest_t = max_dist
        closest_point = None
        hit_wall = None

        for wall in self.walls:
            seg = wall.get_segment()
            p1, p2 = seg.points()
            res = ray_segment_intersection(origin, direction, p1, p2)
            if res is None:
                continue
            t, u = res
            if 0 <= t < closest_t and 0 <= u <= 1:
                closest_t = t
                closest_point = origin + direction * t
                hit_wall = wall

        return closest_point, hit_wall


def angle_diff(a, b):
    # 두 각도 사이의 가장 짧은 방향(양수/음수)으로의 차이 [-pi, pi]
    diff = a - b
    while diff <= -math.pi:
        diff += 2 * math.pi
    while diff > math.pi:
        diff -= math.pi * 2
    return diff


def ray_segment_intersection(origin, direction, a, b):
    # origin : 레이가 시작되는 점(플레이어 위치)
    # direction : 레이의 방향 단위 벡터
    # a, b : 선분의 두 끝점
    # t : 레이 식 "origin + t * direction"에서의 이동량
    # u : 선분 식 "a + u * (b - a)"에서의 상대 위치(0~1 범위일 때 교차)
    # origin + t * direction = a + u*(b-a)
    v1 = origin - a
    v2 = b - a
    denom = direction.cross(v2)
    if abs(denom) < 1e-6:
        return None
    t = v2.cross(v1) / denom
    u = direction.cross(v1) / denom
    if t < 0:
        return None
    return t, u


# =========================
# Scene & Game
# =========================

class Scene:
    def __init__(self):
        self.walls = []
        self.create_default_scene()

    def create_default_scene(self):
        # 기본 방(사각형) + 내부 벽 + 움직이는 벽들
        margin = 50
        w, h = 800, 600
        corners = [
            Vec2(margin, margin),
            Vec2(w - margin, margin),
            Vec2(w - margin, h - margin),
            Vec2(margin, h - margin),
        ]
        # 바깥쪽 벽 (Static)
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            self.walls.append(Wall(p1, p2))

        # 안쪽 벽 (Static)
        self.walls.append(Wall(Vec2(200, 150), Vec2(600, 150)))
        self.walls.append(Wall(Vec2(200, 450), Vec2(600, 450)))
        self.walls.append(Wall(Vec2(250, 200), Vec2(250, 400)))
        self.walls.append(Wall(Vec2(550, 200), Vec2(550, 400)))

        # 움직이는 벽 (Dynamic)
        center = Vec2(400, 300)
        p1 = Vec2(350, 300)
        p2 = Vec2(450, 300)
        self.walls.append(
            Wall(p1, p2, dynamic=True, rotation_center=center, angular_speed=0.5)
        )

        # Dynamic translating wall (좌우로 왕복)
        t_p1 = Vec2(300, 250)
        t_p2 = Vec2(350, 250)
        self.walls.append(
            Wall(t_p1, t_p2, dynamic=True, rotation_center=None, angular_speed=0.0, velocity=Vec2(50, 0))
        )

    def update(self, dt): # Scene.update
        # 벽 업데이트 + 단순 바운스 처리
        for wall in self.walls:
            wall.update(dt)
            if wall.dynamic and wall.velocity.length() > 0:
                seg = wall.get_segment()
                for p in [seg.p1, seg.p2]:
                    if p.x < 80 or p.x > 720:
                        wall.velocity.x *= -1
                    if p.y < 80 or p.y > 520:
                        wall.velocity.y *= -1

    def get_walls(self):
        return self.walls


class Game:
    WIDTH = 800
    HEIGHT = 600

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Visibility Polygon Engine Demo")
        self.clock = pygame.time.Clock()
        self.running = True

        # Engine state
        self.scene = Scene()
        self.visibility_engine = VisibilityEngine(self.scene.get_walls())

        self.player_pos = Vec2(400, 300)
        self.player_speed = 200.0  # pixels per second
        self.player_velocity = Vec2(0, 0)
        self.facing_angle = 0.0
        self.fov_angle = math.radians(90)  # 90 degree FOV
        self.full_360 = False

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_1:
                    # Limited FOV mode
                    self.full_360 = False
                elif event.key == pygame.K_2:
                    # 360-degree mode
                    self.full_360 = True

        keys = pygame.key.get_pressed()
        move = Vec2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1

        if move.length() > 0:
            move = move.normalized() * self.player_speed
        self.player_velocity = move

        # Q/E로 시야 방향 회전
        if keys[pygame.K_q]:
            self.facing_angle -= 2.0 * (1/60.0) * math.pi
        if keys[pygame.K_e]:
            self.facing_angle += 2.0 * (1/60.0) * math.pi

    def update(self, dt):
        # 플레이어 이동
        self.player_pos = self.player_pos + self.player_velocity * dt

        # 화면 밖으로 나가지 않도록 클램프
        self.player_pos.x = max(60, min(self.WIDTH - 60, self.player_pos.x))
        self.player_pos.y = max(60, min(self.HEIGHT - 60, self.player_pos.y))

        # Scene 업데이트(회전/이동하는 벽)
        self.scene.update(dt)

    def draw(self):
        self.screen.fill((20, 20, 30))

        # 가시 다각형 계산
        poly_points, hit_walls = self.visibility_engine.compute_visibility_polygon(
            self.player_pos, self.facing_angle, self.fov_angle, full_360=self.full_360
        )

        # 가시 다각형 그리기 (반투명)
        if len(poly_points) >= 2:
            poly_surface = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
            if self.full_360:
                # 360도 모드: 기존처럼 그대로 사용
                draw_points = [p.tuple() for p in poly_points]
            else:
                # FOV 모드: 플레이어를 꼭짓점으로 포함해서 부채꼴 모양으로 그림
                draw_points = [self.player_pos.tuple()] + [p.tuple() for p in poly_points]

            pygame.draw.polygon(
                poly_surface,
                (255, 255, 100, 60),
                draw_points
            )
            self.screen.blit(poly_surface, (0, 0))

        # 벽 그리기 (가시 다각형에 맞은 벽은 빨간색으로 하이라이트)
        for wall in self.scene.get_walls():
            seg = wall.get_segment()
            color = (120, 120, 120)
            if wall in hit_walls:
                color = (255, 80, 80)  #하이라이트
            pygame.draw.line(
                self.screen,
                color,
                seg.p1.tuple(),
                seg.p2.tuple(),
                3
            )

        # 플레이어
        pygame.draw.circle(self.screen, (80, 200, 255), self.player_pos.tuple(), 8)

        # 시야 방향 표시
        dir_vec = Vec2.from_angle(self.facing_angle) * 40
        pygame.draw.line(
            self.screen,
            (80, 200, 255),
            self.player_pos.tuple(),
            (self.player_pos + dir_vec).tuple(),
            2
        )

        # HUD
        font = pygame.font.SysFont("consolas", 18)
        mode_text = "MODE: 360" if self.full_360 else "MODE: FOV"
        info_lines = [
            "WASD / Arrow Keys: Move",
            "Q/E: Rotate view direction",
            "1: FOV mode (limited)",
            "2: 360 mode",
            mode_text,
        ]
        y = 8
        for line in info_lines:
            surf = font.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (10, y))
            y += 20

        pygame.display.flip()


if __name__ == "__main__":
    Game().run()
