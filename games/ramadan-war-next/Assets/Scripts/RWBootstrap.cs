using UnityEngine;

namespace RamadanWar.Next
{
    /// <summary>Isolated Unity 6 vertical-slice bootstrap. No legacy site/game files are touched.</summary>
    public static class RWBootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void CreateWorld()
        {
            if (Object.FindFirstObjectByType<RWGameState>() != null) return;
            Application.targetFrameRate = Application.isMobilePlatform ? 30 : 60;
            QualitySettings.vSyncCount = 0;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = .007f;
            RenderSettings.fogColor = new Color(.58f, .60f, .59f);
            RenderSettings.ambientLight = new Color(.43f, .44f, .47f);

            var world = new GameObject("Ramadan War Next - Vertical Slice");
            var game = world.AddComponent<RWGameState>();
            BuildLighting(world.transform);
            BuildTrainingCompound(world.transform);
            var player = BuildPlayer(world.transform, game);
            game.Player = player.transform;
            game.PlayerMotor = player;
            BuildObjectives(world.transform, game);
            BuildOpponents(world.transform, game);
        }

        private static Material Material(Color color, float metallic = 0f)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null) shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Unlit/Color");
            var material = new Material(shader);
            material.color = color;
            if (material.HasProperty("_Metallic")) material.SetFloat("_Metallic", metallic);
            if (material.HasProperty("_Smoothness")) material.SetFloat("_Smoothness", .24f);
            return material;
        }

        internal static GameObject Block(Transform parent, string name, Vector3 at, Vector3 size, Color color, bool collider = true)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, true);
            go.transform.position = at;
            go.transform.localScale = size;
            go.GetComponent<Renderer>().sharedMaterial = Material(color);
            if (!collider) Object.Destroy(go.GetComponent<Collider>());
            return go;
        }

        private static void BuildLighting(Transform root)
        {
            var sun = new GameObject("Late afternoon key light");
            sun.transform.SetParent(root);
            sun.transform.rotation = Quaternion.Euler(35f, -32f, 0f);
            var light = sun.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.55f;
            light.color = new Color(1f, .88f, .75f);
            light.shadows = LightShadows.Soft;
            light.shadowStrength = .65f;
            var fill = new GameObject("Blue ambient fill");
            fill.transform.SetParent(root);
            fill.transform.position = new Vector3(0f, 20f, 0f);
            var point = fill.AddComponent<Light>();
            point.type = LightType.Point;
            point.range = 105f;
            point.intensity = 1.15f;
            point.color = new Color(.67f, .78f, 1f);
        }

        private static void BuildTrainingCompound(Transform root)
        {
            Block(root, "180m training valley", new Vector3(0, -.9f, 0), new Vector3(180, 1.8f, 180), new Color(.44f, .41f, .35f));
            var boundary = new Color(.35f, .35f, .33f);
            Block(root, "North perimeter", new Vector3(0, 2f, 88), new Vector3(180, 4, 3), boundary);
            Block(root, "South perimeter", new Vector3(0, 2f, -88), new Vector3(180, 4, 3), boundary);
            Block(root, "West perimeter", new Vector3(-88, 2f, 0), new Vector3(3, 4, 180), boundary);
            Block(root, "East perimeter", new Vector3(88, 2f, 0), new Vector3(3, 4, 180), boundary);
            Block(root, "Main route", new Vector3(-4, .03f, 0), new Vector3(13, .06f, 166), new Color(.27f, .27f, .27f));
            Block(root, "Cross road", new Vector3(0, .04f, 18), new Vector3(163, .06f, 10), new Color(.29f, .29f, .30f));

            for (var i = 0; i < 16; i++)
            {
                var x = -68f + (i % 4) * 44f;
                var z = -44f + (i / 4) * 30f;
                // Leave road and mission objectives traversable.
                if (Mathf.Abs(x) < 14f || Mathf.Abs(z - 18f) < 8f) continue;
                var tall = (i % 3 == 0) ? 7.5f : 3.8f;
                Block(root, "Training building " + i, new Vector3(x, tall / 2, z), new Vector3(12, tall, 15),
                    new Color(.45f + (i % 3) * .045f, .42f, .36f));
                Block(root, "Roof trim " + i, new Vector3(x, tall + .22f, z), new Vector3(13, .4f, 16), new Color(.25f, .29f, .28f));
            }
            for (var i = 0; i < 26; i++)
            {
                var x = -72f + ((i * 31) % 143);
                var z = -70f + ((i * 19) % 147);
                if (Mathf.Abs(x) < 9f || Mathf.Abs(z - 18f) < 8f) continue;
                Block(root, "Low tactical cover " + i, new Vector3(x, .9f, z),
                    new Vector3(3.3f + i % 3, 1.8f, 1.2f + i % 2), new Color(.34f, .38f, .38f));
            }
            for (var i = 0; i < 5; i++)
            {
                var z = -55f + i * 29f;
                Block(root, "Lamp post " + i, new Vector3(7f, 4f, z), new Vector3(.32f, 8f, .32f), new Color(.22f, .24f, .24f));
                Block(root, "Light housing " + i, new Vector3(7f, 8.1f, z), new Vector3(1.9f, .4f, .8f), new Color(.84f, .76f, .56f));
            }
            Block(root, "Radar platform", new Vector3(44, 1f, 25), new Vector3(21, 2, 20), new Color(.35f, .37f, .40f));
            Block(root, "Radar mast", new Vector3(44, 10f, 25), new Vector3(1.2f, 18, 1.2f), new Color(.32f, .42f, .40f));
            Block(root, "Radar antenna", new Vector3(44, 19f, 25), new Vector3(16, 1.2f, 2f), new Color(.26f, .36f, .37f));
            Block(root, "Extraction pad", new Vector3(67, .1f, 67), new Vector3(20, .2f, 20), new Color(.15f, .33f, .35f));
            Block(root, "Extraction marking A", new Vector3(67, .22f, 67), new Vector3(15, .03f, 1), new Color(.85f, .71f, .26f), false);
            Block(root, "Extraction marking B", new Vector3(67, .23f, 67), new Vector3(1, .03f, 15), new Color(.85f, .71f, .26f), false);
        }

        private static RWPlayerMotor BuildPlayer(Transform root, RWGameState game)
        {
            var actor = new GameObject("Player");
            actor.transform.SetParent(root);
            actor.transform.position = new Vector3(-65, .08f, -65);
            var cc = actor.AddComponent<CharacterController>();
            cc.radius = .38f;
            cc.height = 1.8f;
            cc.center = new Vector3(0, .9f, 0);
            cc.stepOffset = .3f;
            cc.slopeLimit = 50;
            var eye = new GameObject("First-person Camera");
            eye.transform.SetParent(actor.transform);
            eye.transform.localPosition = new Vector3(0, 1.62f, 0);
            eye.tag = "MainCamera";
            var camera = eye.AddComponent<Camera>();
            camera.fieldOfView = 70;
            camera.nearClipPlane = .05f;
            camera.farClipPlane = 210f;
            eye.AddComponent<AudioListener>();
            var motor = actor.AddComponent<RWPlayerMotor>();
            motor.Game = game;
            motor.Eye = camera;
            motor.Controller = cc;
            return motor;
        }

        private static void BuildObjectives(Transform root, RWGameState game)
        {
            var relayColor = new Color(.10f, .7f, .78f);
            Objective(root, game, "South communications relay", new Vector3(-40, 0, -9), RWObjective.Kind.Relay, relayColor);
            Objective(root, game, "North communications relay", new Vector3(38, 0, -17), RWObjective.Kind.Relay, relayColor);
            var intelColor = new Color(.92f, .73f, .24f);
            Objective(root, game, "Intel cache Alpha", new Vector3(-61, 0, 32), RWObjective.Kind.Intel, intelColor);
            Objective(root, game, "Intel cache Bravo", new Vector3(11, 0, 44), RWObjective.Kind.Intel, intelColor);
            Objective(root, game, "Intel cache Charlie", new Vector3(56, 0, 39), RWObjective.Kind.Intel, intelColor);
            Objective(root, game, "Extraction beacon", new Vector3(67, 0, 67), RWObjective.Kind.Extraction, new Color(.27f, .94f, .41f));
        }

        private static void Objective(Transform root, RWGameState game, string name, Vector3 at, RWObjective.Kind kind, Color color)
        {
            var column = Block(root, name, at + new Vector3(0, 1.25f, 0), new Vector3(1.8f, 2.5f, 1.8f), color);
            var target = column.AddComponent<RWObjective>();
            target.Type = kind;
            target.Game = game;
            var glow = new GameObject("Beacon glow").AddComponent<Light>();
            glow.type = LightType.Point;
            glow.range = 9f;
            glow.intensity = 2.2f;
            glow.color = color;
            glow.transform.SetParent(column.transform, false);
            glow.transform.localPosition = new Vector3(0, .65f, 0);
            game.Objectives.Add(target);
        }

        private static void BuildOpponents(Transform root, RWGameState game)
        {
            var positions = new Vector3[] {
                new(-52,0,-27), new(-29,0,-12), new(8,0,-31), new(27,0,-3),
                new(-49,0,33), new(-19,0,44), new(26,0,33), new(60,0,24),
                new(17,0,63), new(-25,0,67), new(58,0,57), new(43,0,-46),
            };
            for (var i = 0; i < positions.Length; i++)
            {
                var soldier = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                soldier.name = "Opponent " + (i + 1);
                soldier.transform.SetParent(root);
                soldier.transform.position = positions[i] + Vector3.up;
                soldier.transform.localScale = new Vector3(.7f, 1.08f, .7f);
                soldier.GetComponent<Renderer>().sharedMaterial = Material(
                    i % 3 == 0 ? new Color(.33f, .37f, .28f) : new Color(.42f, .34f, .27f));
                var ai = soldier.AddComponent<RWEnemyBrain>();
                ai.Game = game;
                ai.Role = (RWEnemyBrain.RoleType)(i % 3);
                ai.Home = soldier.transform.position;
            }
        }
    }
}
