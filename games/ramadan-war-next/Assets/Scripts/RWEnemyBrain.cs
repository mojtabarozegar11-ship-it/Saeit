using UnityEngine;

namespace RamadanWar.Next
{
    /// <summary>Three-role tactical enemy FSM: patrol, investigate, reposition and suppress.</summary>
    public sealed class RWEnemyBrain : MonoBehaviour
    {
        public enum RoleType { Patrol, Flanker, Suppressor }
        private enum Behaviour { Patrol, Alert, Advance, Flank, Suppress, Retreat }
        public RWGameState Game;
        public RoleType Role;
        public Vector3 Home;
        private Behaviour behaviour;
        private float health = 100f;
        private float nextDecision, nextFire, nextPatrol, alertUntil, staggerUntil;
        private Vector3 destination, velocity;
        private Renderer renderComponent;
        private Color originalColor;
        private float hurtUntil;
        private bool dead;

        private void Start()
        {
            renderComponent = GetComponentInChildren<Renderer>();
            // Character prefabs may keep the visible mesh on a child. Missing art must not crash AI.
            if (renderComponent != null) originalColor = renderComponent.material.color;
            destination = Home + new Vector3(Random.Range(-8f,8f),0,Random.Range(-8f,8f));
            nextFire = Time.time + Random.Range(.8f, 2.1f);
        }

        private void Update()
        {
            if (dead || Game == null || Game.Player == null ||
                Game.Phase == RWGameState.MissionPhase.Victory) return;
            if (renderComponent != null && Time.time > hurtUntil)
                renderComponent.material.color = originalColor;
            var target = Game.Player.position + Vector3.up;
            var relative = target - transform.position;
            var distance = relative.magnitude;
            var lineOfSight = distance < 58f && CanSee(target);
            if (lineOfSight) alertUntil = Time.time + 7f;

            if (Time.time >= nextDecision)
            {
                nextDecision = Time.time + Random.Range(.65f, 1.25f);
                Decide(distance, lineOfSight, target);
            }
            if (Time.time < staggerUntil) return;
            if (behaviour == Behaviour.Suppress && lineOfSight && distance < 47f)
            {
                transform.rotation = Quaternion.Slerp(transform.rotation,
                    Quaternion.LookRotation(new Vector3(relative.x,0,relative.z)), 5f * Time.deltaTime);
                FireAt(target, distance);
            }
            else if (behaviour == Behaviour.Advance || behaviour == Behaviour.Flank ||
                     behaviour == Behaviour.Retreat || behaviour == Behaviour.Patrol ||
                     behaviour == Behaviour.Alert)
            {
                MoveTowards(destination, Time.deltaTime);
                if (lineOfSight && distance < 42f) FireAt(target, distance);
            }
        }

        private void Decide(float distance, bool seen, Vector3 playerPosition)
        {
            if (!seen && Time.time > alertUntil)
            {
                behaviour = Behaviour.Patrol;
                if (Vector3.Distance(transform.position, destination) < 2f || Time.time > nextPatrol)
                {
                    destination = Home + new Vector3(Random.Range(-13f,13f),0,Random.Range(-13f,13f));
                    nextPatrol = Time.time + Random.Range(5f,10f);
                }
                return;
            }
            if (!seen)
            {
                behaviour = Behaviour.Alert;
                destination = playerPosition;
                return;
            }
            if (health < 35 && distance < 17)
            {
                behaviour = Behaviour.Retreat;
                destination = transform.position +
                    (transform.position - playerPosition).normalized * 12f;
                return;
            }
            if (Role == RoleType.Suppressor && distance < 38f)
            {
                behaviour = Behaviour.Suppress;
                destination = transform.position;
                return;
            }
            if (Role == RoleType.Flanker && distance < 40f)
            {
                behaviour = Behaviour.Flank;
                var toTarget = (playerPosition - transform.position).normalized;
                var lateral = Vector3.Cross(Vector3.up, toTarget) * (GetInstanceID() % 2 == 0 ? 1 : -1);
                destination = playerPosition - toTarget * 13f + lateral * 12f;
                return;
            }
            if (distance < 14)
            {
                behaviour = Behaviour.Suppress;
                return;
            }
            behaviour = Behaviour.Advance;
            destination = playerPosition - (playerPosition - transform.position).normalized * 11f;
        }

        private bool CanSee(Vector3 target)
        {
            var start = transform.position + Vector3.up * .32f;
            var displacement = target - start;
            if (Physics.Raycast(start, displacement.normalized, out var hit, displacement.magnitude,
                    ~0, QueryTriggerInteraction.Ignore))
            {
                var motor = hit.collider.GetComponentInParent<RWPlayerMotor>();
                return motor != null;
            }
            return false;
        }

        private void MoveTowards(Vector3 target, float dt)
        {
            var planar = target - transform.position;
            planar.y = 0;
            if (planar.sqrMagnitude < 2.5f) return;
            var heading = planar.normalized;
            var start = transform.position + Vector3.up*.1f;
            if (Physics.Raycast(start, heading, 1.45f, ~0, QueryTriggerInteraction.Ignore))
            {
                var side = Vector3.Cross(Vector3.up, heading);
                heading = (heading * .3f + side * (GetInstanceID() % 2 == 0 ? 1f : -1f)).normalized;
            }
            var speed = Role == RoleType.Flanker ? 4.4f : Role == RoleType.Patrol ? 3.1f : 2.6f;
            velocity = Vector3.Lerp(velocity, heading * speed, Mathf.Min(1f,dt*4f));
            transform.position += velocity * dt;
            transform.rotation = Quaternion.Slerp(transform.rotation,
                Quaternion.LookRotation(heading), Mathf.Min(1f,dt*5f));
            var pos = transform.position;
            pos.x = Mathf.Clamp(pos.x, -84, 84);
            pos.z = Mathf.Clamp(pos.z, -84, 84);
            pos.y = 1.08f;
            transform.position = pos;
        }

        private void FireAt(Vector3 target, float distance)
        {
            if (Time.time < nextFire) return;
            nextFire = Time.time + (Role == RoleType.Suppressor ? 1.2f :
                Role == RoleType.Flanker ? 1.8f : 2.25f) + Random.Range(0f,.4f);
            if (!CanSee(target)) return;
            // Distance- and posture-dependent accuracy, never guaranteed hits.
            var chance = Mathf.Clamp01(.58f - distance * .006f +
                (Role == RoleType.Suppressor ? .11f : 0f));
            if (Random.value <= chance) Game.TakeDamage(Role == RoleType.Suppressor ? 5f : 8f);
        }

        public void ReceiveHit(float damage)
        {
            if (dead) return;
            health -= damage;
            staggerUntil = Time.time + .15f;
            hurtUntil = Time.time + .15f;
            if (renderComponent != null) renderComponent.material.color = new Color(1f,.28f,.15f);
            alertUntil = Time.time + 9f;
            if (health > 0) return;
            dead = true;
            Game.EnemyDefeated();
            Destroy(gameObject);
        }
    }
}
