using System.Collections.Generic;
using UnityEngine;

namespace RamadanWar.Next
{
    /// <summary>Explicit mission state machine. Objectives cannot be silently skipped.</summary>
    public sealed class RWGameState : MonoBehaviour
    {
        public enum MissionPhase { Relays, Intel, Extraction, Victory }
        public readonly List<RWObjective> Objectives = new();
        public Transform Player;
        public RWPlayerMotor PlayerMotor;
        public MissionPhase Phase { get; private set; } = MissionPhase.Relays;
        public int RelayCount { get; private set; }
        public int IntelCount { get; private set; }
        public int Kills { get; private set; }
        public int Lives { get; private set; } = 100;
        public float Health { get; private set; } = 100;
        public string Notice { get; private set; } = "دو مرکز ارتباطی را از کار بیندازید";
        private float noticeUntil;
        private float invulnerableUntil;
        private GUIStyle titleStyle, secondaryStyle, buttonStyle;

        public RWObjective CurrentObjective
        {
            get
            {
                var desired = Phase == MissionPhase.Relays ? RWObjective.Kind.Relay :
                    Phase == MissionPhase.Intel ? RWObjective.Kind.Intel : RWObjective.Kind.Extraction;
                foreach (var target in Objectives)
                    if (!target.Activated && target.Type == desired) return target;
                return null;
            }
        }

        public void TryInteract()
        {
            if (Phase == MissionPhase.Victory || Player == null) return;
            RWObjective nearest = null;
            var best = 4f;
            foreach (var objective in Objectives)
            {
                if (objective.Activated) continue;
                var dist = Vector3.Distance(Player.position, objective.transform.position);
                if (dist < best) { best = dist; nearest = objective; }
            }
            if (nearest == null) { Announce("برای تعامل به هدف نزدیک شوید"); return; }

            var requiredKind = Phase == MissionPhase.Relays ? RWObjective.Kind.Relay :
                Phase == MissionPhase.Intel ? RWObjective.Kind.Intel : RWObjective.Kind.Extraction;
            if (nearest.Type != requiredKind) { Announce("ابتدا هدف فعلی مأموریت را تکمیل کنید"); return; }
            if (requiredKind == RWObjective.Kind.Extraction && Kills < 4)
            {
                Announce("پیش از خروج حداقل چهار مهاجم را متوقف کنید");
                return;
            }

            nearest.Activated = true;
            nearest.gameObject.GetComponent<Renderer>().material.color = new Color(.17f, .23f, .22f);
            foreach (var light in nearest.GetComponentsInChildren<Light>()) light.enabled = false;

            switch (nearest.Type)
            {
                case RWObjective.Kind.Relay:
                    RelayCount++;
                    Announce("سامانه قطع شد — " + RelayCount + " / 2");
                    if (RelayCount == 2) { Phase = MissionPhase.Intel; Announce("حالا سه بسته اطلاعاتی را بازیابی کنید"); }
                    break;
                case RWObjective.Kind.Intel:
                    IntelCount++;
                    Announce("اطلاعات بازیابی شد — " + IntelCount + " / 3");
                    if (IntelCount == 3) { Phase = MissionPhase.Extraction; Announce("به نقطه خروج برسید — پس از مهار چهار مهاجم"); }
                    break;
                case RWObjective.Kind.Extraction:
                    Phase = MissionPhase.Victory;
                    Announce("مأموریت با موفقیت پایان یافت");
                    PlayerPrefs.SetInt("rw_next_slice_completed", 1);
                    PlayerPrefs.Save();
                    if (PlayerMotor != null) PlayerMotor.SetFinished();
                    break;
            }
        }

        public void EnemyDefeated()
        {
            Kills++;
            if (Phase == MissionPhase.Extraction && Kills == 4) Announce("منطقه امن شد؛ به نقطه خروج بروید");
        }

        public void TakeDamage(float amount)
        {
            if (Phase == MissionPhase.Victory || Time.time < invulnerableUntil) return;
            Health = Mathf.Max(0, Health - amount);
            invulnerableUntil = Time.time + .45f;
            if (Health > 0) return;
            Lives--;
            if (Lives <= 0)
            {
                Lives = 100; // User preference: a forgiving, high-life arcade FPS.
                Announce("جان‌های تازه دریافت شد");
            }
            Health = 100f;
            invulnerableUntil = Time.time + 3f;
            PlayerMotor?.Respawn();
        }

        public void Announce(string message)
        {
            Notice = message;
            noticeUntil = Time.time + 4f;
        }

        private void OnGUI()
        {
            if (Player == null) return;
            if (titleStyle == null)
            {
                titleStyle = new GUIStyle(GUI.skin.label) {
                    fontSize = Mathf.Clamp(Screen.height / 34, 15, 29), fontStyle = FontStyle.Bold,
                    normal = { textColor = Color.white }, alignment = TextAnchor.MiddleRight
                };
                secondaryStyle = new GUIStyle(GUI.skin.label) {
                    fontSize = Mathf.Clamp(Screen.height / 49, 12, 22),
                    normal = { textColor = new Color(.78f,.91f,.92f) }, alignment = TextAnchor.MiddleRight
                };
                buttonStyle = new GUIStyle(GUI.skin.box) {
                    fontSize = Mathf.Clamp(Screen.height / 40, 13, 24), alignment = TextAnchor.MiddleCenter,
                    normal = { textColor = Color.white }
                };
            }

            var w = Screen.width; var h = Screen.height;
            GUI.Box(new Rect(w - Mathf.Min(490,w*.76f) - 15, 8, Mathf.Min(490,w*.76f), 119), "");
            GUI.Label(new Rect(w-350, 10, 328, 31), "جنگ رمضان — نمونه مهندسی Unity", titleStyle);
            GUI.Label(new Rect(w-350, 42, 328, 30), "سلامت " + Mathf.CeilToInt(Health) + " | جان " + Lives +
                      " | حذف دشمن " + Kills, secondaryStyle);
            GUI.Label(new Rect(w-350, 74, 328, 28), PlayerMotor == null ? "" :
                "مهمات " + PlayerMotor.Ammo + " / " + PlayerMotor.Reserve, secondaryStyle);

            var phaseLabel = Phase == MissionPhase.Relays ? "قطع دو سامانه " + RelayCount + "/2" :
                Phase == MissionPhase.Intel ? "بازیابی اطلاعات " + IntelCount + "/3" :
                Phase == MissionPhase.Extraction ? "رسیدن به خروج؛ دشمن " + Kills + "/4" : "پیروزی";
            GUI.Box(new Rect(12, 10, Mathf.Min(420, w*.6f), 82), "");
            GUI.Label(new Rect(22, 13, Mathf.Min(400,w*.57f), 29), phaseLabel, titleStyle);
            var target = CurrentObjective;
            if (target != null)
            {
                var meters = Vector3.Distance(Player.position, target.transform.position);
                GUI.Label(new Rect(22, 43, Mathf.Min(400,w*.57f), 32),
                    target.gameObject.name + " — " + Mathf.RoundToInt(meters) + "m", secondaryStyle);
            }
            if (Time.time < noticeUntil)
            {
                var boxWidth = Mathf.Min(w * .82f, 650f);
                GUI.Box(new Rect((w-boxWidth)/2, 100, boxWidth, 48), "");
                GUI.Label(new Rect((w-boxWidth)/2+9, 105, boxWidth-18, 38), Notice, secondaryStyle);
            }
            if (Phase == MissionPhase.Victory)
            {
                var width = Mathf.Min(620f, w*.85f);
                GUI.Box(new Rect((w-width)/2, h*.30f, width, 100), "");
                GUI.Label(new Rect((w-width)/2+10,h*.32f,width-20,78),
                    "مأموریت تمام شد! نسخهٔ آزمایشی — امتیاز کیفیت هنوز تأیید نشده", titleStyle);
            }
            if (Application.isMobilePlatform)
            {
                GUI.Box(new Rect(12, h-180, 155, 155), "حرکت");
                GUI.Box(new Rect(w-136, h-155, 125, 125), "شلیک");
                GUI.Box(new Rect(w-136, 32, 125, 76), "تعامل");
                GUI.Box(new Rect(w-250, h-96, 105, 76), "خشاب");
            }
            else if (Cursor.lockState != CursorLockMode.Locked)
            {
                GUI.Box(new Rect(w*.33f, h*.78f, w*.34f, 48), "برای فعال‌کردن نشانه‌گیری کلیک کنید");
            }
            GUI.Label(new Rect(w/2-13, h/2-20, 26, 40), "+", titleStyle);
        }
    }

    public sealed class RWObjective : MonoBehaviour
    {
        public enum Kind { Relay, Intel, Extraction }
        public Kind Type;
        public RWGameState Game;
        public bool Activated;
        private float baseY;
        private void Start() { baseY = transform.position.y; }
        private void Update()
        {
            if (Activated) return;
            // Subtle glow pulse, without moving the interaction collider.
            foreach (var light in GetComponentsInChildren<Light>())
                light.intensity = 1.7f + Mathf.Sin(Time.time * 2.6f) * .5f;
        }
    }
}
