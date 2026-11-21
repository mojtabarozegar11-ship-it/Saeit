using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RamadanWar.Next.Editor
{
    /// <summary>Single project, isolated output folders. Deliberately no live deployment.</summary>
    public static class RWBuild
    {
        private const string ScenePath = "Assets/Scenes/RWGenerated.unity";

        [MenuItem("Tools/Ramadan War Next/Build Web")]
        public static void BuildWeb()
        {
            Build(BuildTarget.WebGL, "Builds/Web");
        }

        [MenuItem("Tools/Ramadan War Next/Build Android")]
        public static void BuildAndroid()
        {
            Build(BuildTarget.Android, "Builds/Android/RamadanWarNext.apk");
        }

        private static void Build(BuildTarget target, string output)
        {
            Directory.CreateDirectory("Assets/Scenes");
            Directory.CreateDirectory(Path.GetDirectoryName(output) ?? ".");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            if (!EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), ScenePath))
                throw new InvalidOperationException("Could not save isolated build scene.");
            AssetDatabase.Refresh();

            PlayerSettings.companyName = "Zomorod Melal";
            PlayerSettings.productName = "Ramadan War Next — Engineering Slice";
            PlayerSettings.SetApplicationIdentifier(
                UnityEditor.Build.NamedBuildTarget.FromBuildTargetGroup(BuildPipeline.GetBuildTargetGroup(target)),
                "ir.zomorodmelal.ramadanwarnext");
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 720;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] { ScenePath },
                locationPathName = output,
                target = target,
                options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException(
                    "Unity " + target + " build failed: " + report.summary.result +
                    "; errors " + report.summary.totalErrors);
            Debug.Log("RAMADAN_NEXT_" + target + "_BUILD=PASS; bytes=" + report.summary.totalSize);
        }
    }
}
