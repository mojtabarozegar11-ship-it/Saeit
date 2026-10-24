using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch;
using Touch = UnityEngine.InputSystem.EnhancedTouch.Touch;

namespace RamadanWar.Next
{
    /// <summary>FPS locomotion, dual-input aiming, recoil and hitscan combat. No server dependency.</summary>
    public sealed class RWPlayerMotor : MonoBehaviour
    {
        public RWGameState Game;
        public Camera Eye;
        public CharacterController Controller;
        public int Ammo { get; private set; } = 30;
        public int Reserve { get; private set; } = 240;
        private const int Magazine = 30;
        private float pitch, verticalVelocity, nextShot, reloadEnd, bobTime;
        private bool reloading, finished, ads;
        private Vector2 touchMove, touchLook;
        private bool touchFire, touchInteract, touchReload;
        private Transform gun;
        private Vector3 gunRest;
        private float recoil;
        private float headBob;

        private void Awake()
        {
            EnhancedTouchSupport.Enable();
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        private void Start()
        {
            // Temporary equipment blockout; replace only with licensed, complete animated assets.
            var frame = RWBootstrap.Block(Eye.transform, "FP weapon placeholder", new Vector3(.34f, -.26f, .66f),
                new Vector3(.16f, .17f, .78f), new Color(.22f,.29f,.29f), false);
            frame.transform.SetParent(Eye.transform, false);
            frame.transform.localPosition = new Vector3(.34f,-.27f,.68f);
            gun = frame.transform;
            gunRest = gun.localPosition;
        }

        private void Update()
        {
            if (finished || Game == null) return;
            ReadTouchInput();
            var keyboard = Keyboard.current;
            var mouse = Mouse.current;
            var pad = Gamepad.current;

            if (keyboard != null && keyboard.escapeKey.wasPressedThisFrame)
            {
                Cursor.lockState = CursorLockMode.None;
                Cursor.visible = true;
            }
            if (mouse != null && mouse.leftButton.wasPressedThisFrame && Cursor.lockState != CursorLockMode.Locked)
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
            }

            float forward = Axis(keyboard, Key.W, Key.S);
            float side = Axis(keyboard, Key.D, Key.A);
            bool running = keyboard != null && keyboard.leftShiftKey.isPressed;
            if (pad != null)
            {
                var stick = pad.leftStick.ReadValue();
                forward += stick.y; side += stick.x;
                running |= pad.leftStickButton.isPressed;
            }
            forward += touchMove.y;
            side += touchMove.x;
            var localMove = Vector3.ClampMagnitude(new Vector3(side, 0, forward), 1f);
            var speed = running ? 8.4f : 5.4f;
            var worldMove = transform.TransformDirection(localMove) * speed;
            if (Controller.isGrounded) verticalVelocity = -.5f;
            else verticalVelocity -= 20f * Time.deltaTime;
            worldMove.y = verticalVelocity;
            Controller.Move(worldMove * Time.deltaTime);
            bobTime += Time.deltaTime * localMove.magnitude * (running ? 12f : 9f);

            var look = Vector2.zero;
            if (mouse != null && Cursor.lockState == CursorLockMode.Locked) look += mouse.delta.ReadValue() * .095f;
            if (pad != null) look += pad.rightStick.ReadValue() * (115f * Time.deltaTime);
            look += touchLook * .065f;
            var sensitivity = ads ? .55f : 1f;
            transform.Rotate(Vector3.up, look.x * sensitivity, Space.Self);
            pitch = Mathf.Clamp(pitch - look.y * sensitivity, -80f, 83f);
            Eye.transform.localRotation = Quaternion.Euler(pitch - recoil * 1.8f, 0, 0);

            ads = (mouse != null && mouse.rightButton.isPressed) ||
                  (pad != null && pad.leftTrigger.ReadValue() > .4f);
            Eye.fieldOfView = Mathf.Lerp(Eye.fieldOfView, ads ? 48f : 70f, 10f * Time.deltaTime);

            if (reloading && Time.time >= reloadEnd)
            {
                var loaded = Mathf.Min(Magazine - Ammo, Reserve);
                Ammo += loaded; Reserve -= loaded; reloading = false;
            }
            bool requestedReload = (keyboard != null && keyboard.rKey.wasPressedThisFrame) ||
                                   (pad != null && pad.buttonWest.wasPressedThisFrame) || touchReload;
            if (requestedReload) Reload();
            if ((keyboard != null && keyboard.gKey.wasPressedThisFrame) ||
                (pad != null && pad.buttonNorth.wasPressedThisFrame) || touchInteract)
                Game.TryInteract();

            var firing = (mouse != null && mouse.leftButton.isPressed && Cursor.lockState == CursorLockMode.Locked) ||
                         (pad != null && pad.rightTrigger.ReadValue() > .3f) || touchFire;
            if (firing) Fire();
            recoil = Mathf.MoveTowards(recoil, 0, 5.5f * Time.deltaTime);
            headBob = Mathf.Lerp(headBob, Mathf.Sin(bobTime) * .011f * localMove.magnitude, 8f * Time.deltaTime);
            if (gun != null) gun.localPosition = Vector3.Lerp(gun.localPosition,
                gunRest + new Vector3(ads ? -.19f : 0, headBob, -recoil*.08f), 16f * Time.deltaTime);
        }

        private static float Axis(Keyboard keyboard, Key positive, Key negative)
        {
            if (keyboard == null) return 0f;
            return (keyboard[positive].isPressed ? 1f : 0f) - (keyboard[negative].isPressed ? 1f : 0f);
        }

        private void ReadTouchInput()
        {
            touchMove = Vector2.zero;
            touchLook = Vector2.zero;
            touchFire = false;
            touchInteract = false;
            touchReload = false;
            foreach (var touch in Touch.activeTouches)
            {
                var at = touch.screenPosition;
                if (at.x < Screen.width * .42f)
                {
                    touchMove += Vector2.ClampMagnitude(
                        (at - touch.startScreenPosition) / (Screen.height * .11f), 1f);
                }
                else if (at.x > Screen.width * .77f && at.y < Screen.height * .37f)
                {
                    touchFire = true;
                }
                else if (at.x > Screen.width * .77f && at.y > Screen.height * .72f)
                {
                    if (touch.phase == UnityEngine.InputSystem.TouchPhase.Began) touchInteract = true;
                }
                else if (at.x > Screen.width * .60f && at.x <= Screen.width*.77f &&
                         at.y < Screen.height*.26f)
                {
                    if (touch.phase == UnityEngine.InputSystem.TouchPhase.Began) touchReload = true;
                }
                else { touchLook += touch.delta; }
            }
        }

        private void Reload()
        {
            if (reloading || Ammo >= Magazine || Reserve <= 0) return;
            reloading = true;
            reloadEnd = Time.time + 1.35f;
            Game.Announce("تعویض خشاب ...");
        }

        private void Fire()
        {
            if (Time.time < nextShot || reloading) return;
            if (Ammo == 0) { Reload(); return; }
            nextShot = Time.time + .115f;
            Ammo--;
            recoil = Mathf.Clamp(recoil + .65f, 0f, 2f);
            var spread = ads ? .0038f : .014f;
            var direction = (Eye.transform.forward +
                Eye.transform.right * Random.Range(-spread, spread) +
                Eye.transform.up * Random.Range(-spread, spread)).normalized;
            var ray = new Ray(Eye.transform.position, direction);
            var endpoint = ray.GetPoint(100f);
            if (Physics.Raycast(ray, out var hit, 100f, ~0, QueryTriggerInteraction.Ignore))
            {
                endpoint = hit.point;
                var enemy = hit.collider.GetComponentInParent<RWEnemyBrain>();
                if (enemy != null) enemy.ReceiveHit(ads ? 37 : 28);
            }
            Tracer(Eye.transform.position + Eye.transform.forward * .45f, endpoint);
        }

        private static void Tracer(Vector3 start, Vector3 end)
        {
            var obj = new GameObject("Brief bullet tracer");
            var line = obj.AddComponent<LineRenderer>();
            line.positionCount = 2;
            line.SetPosition(0, start); line.SetPosition(1, end);
            line.startWidth = .014f; line.endWidth = .003f;
            line.material = new Material(Shader.Find("Sprites/Default"));
            line.startColor = new Color(1, .8f, .3f, .8f);
            line.endColor = new Color(1, .3f, .1f, 0f);
            Object.Destroy(obj, .075f);
        }

        public void Respawn()
        {
            Controller.enabled = false;
            transform.position = new Vector3(-65f, .12f, -65f);
            Controller.enabled = true;
            Game.Announce("بازگشت به مأموریت؛ ۱۰۰ واحد سلامت");
        }

        public void SetFinished()
        {
            finished = true;
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
    }
}
