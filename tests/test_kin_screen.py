import os
import tempfile
import unittest
from pathlib import Path

import pygame

from simulation.events.event import DomainEvent
from simulation.family.children import CARRIED, GROUND
from simulation.family.family_system import SLEEP_ROUGH_ACTION
from simulation.health.injury import Death
from simulation.residents.activity import Activity
from simulation.substances.substance import Habit, Intake
from simulation.world import SimulationWorld
from ui.family_tree import ADOPTIVE, CARRIED as TREE_CARRIED, DEAD, ELSEWHERE, HERE, PARENT, SIBLING, SPOUSE, family_tree
from ui.labels import (
    KIN_CARRIED,
    KIN_DEAD,
    KIN_ELSEWHERE,
    describe_action,
    describe_age,
    describe_date,
    describe_identity,
    family_notes,
    habit_rows,
    has_birthday,
    kin_rows,
)

DAYS_PER_YEAR = 365


def _family(world: SimulationWorld) -> tuple[str, str]:
    """Have Marta and Raúl marry and have two children: one of ten who walks, and one still
    carried. Returns the IDs of the two, the elder first."""
    marta, raul = world.residents["marta"], world.residents["raul"]
    marta.couple_with, raul.couple_with = "raul", "marta"
    world.kinship["marta"].spouse, world.kinship["raul"].spouse = "raul", "marta"
    marta.expecting_with = "raul"
    elder = world.children.give_birth(world, marta)
    elder.born = world.clock.day - world.children.settings(world).weeks * 7 - 1
    world.children.tick_day(world)
    marta.expecting_with = "raul"
    younger = world.children.give_birth(world, marta)
    return elder.child_id, younger.child_id


class FamilyTreeTests(unittest.TestCase):
    """The families of the whole settlement, laid out (no pygame)."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world(seed=7)

    def test_everybody_on_record_is_on_it_once_and_nobody_on_top_of_anybody(self) -> None:
        tree = family_tree(self.world)
        self.assertEqual(set(tree.places), set(tree.people))
        self.assertTrue(set(self.world.residents) <= set(tree.places))
        self.assertEqual(len(set(tree.places.values())), len(tree.places))
        for column, row in tree.places.values():
            self.assertTrue(0 <= column < tree.size[0] and 0 <= row < tree.size[1])

    def test_brothers_and_sisters_are_side_by_side_and_whoever_never_came_is_there_too(self) -> None:
        tree = family_tree(self.world)
        self.assertEqual(tree.places["marta"][1], tree.places["vera"][1])
        self.assertIn(("marta", "vera"), [(tie.one, tie.other) for tie in tree.ties if tie.kind == SIBLING])
        self.assertEqual(tree.people["bruno"].state, ELSEWHERE, "Paco's brother has not come to the gate")
        self.assertEqual(tree.places["bruno"][1], tree.places["paco"][1])
        self.assertIn("ines", tree.alone)
        self.assertNotIn("marta", tree.alone)

    def test_children_are_under_their_parents_who_stand_together(self) -> None:
        elder, younger = _family(self.world)
        tree = family_tree(self.world)
        marta, raul = tree.places["marta"], tree.places["raul"]
        self.assertEqual(marta[1], raul[1])
        self.assertEqual(abs(marta[0] - raul[0]), 1.0, "the two of them side by side")
        for child in (elder, younger):
            self.assertEqual(tree.places[child][1], marta[1] + 1)
        self.assertEqual((tree.people[elder].state, tree.people[younger].state), (HERE, TREE_CARRIED))
        kinds = {(tie.kind, tie.one, tie.other) for tie in tree.ties}
        self.assertIn((PARENT, "marta", elder), kinds)
        self.assertIn((PARENT, "raul", younger), kinds)
        self.assertEqual(len([tie for tie in tree.ties if tie.kind == SPOUSE]), 1, "married, and so not also a couple")
        self.assertEqual(tree.places["vera"][1], marta[1], "and her sister is still beside them")

    def test_the_dead_stay_on_it_and_whoever_was_taken_in_is_tied_as_such(self) -> None:
        elder, younger = _family(self.world)
        world = self.world
        world.kinship[younger].adoptive.append("ines")
        bundle = world.bundles.pop(younger)
        world.deaths.append(Death(younger, bundle.name, world.clock.total_minutes, "el abandono"))
        tree = family_tree(world)
        self.assertEqual(tree.people[younger].state, DEAD)
        self.assertIn(younger, tree.places)
        self.assertIn((ADOPTIVE, "ines", younger), {(tie.kind, tie.one, tie.other) for tie in tree.ties})
        self.assertNotIn("ines", tree.alone)

    def test_with_nobody_there_is_nothing(self) -> None:
        tree = family_tree(SimulationWorld.new_settlement(3))
        self.assertEqual((tree.places, tree.size), ({}, (0.0, 0.0)))


class KinLabelTests(unittest.TestCase):
    """What is said of who somebody is, whose they are and what they take (no pygame)."""

    def setUp(self) -> None:
        self.world = SimulationWorld.demo_world(seed=7)
        self.marta = self.world.residents["marta"]

    def test_who_they_are_is_said_in_words(self) -> None:
        marta = self.marta
        marta.sex, marta.gender, marta.drawn_to = "f", "f", "m"
        self.assertEqual(describe_identity(self.world, marta), "Mujer · le atraen los hombres")
        marta.gender, marta.drawn_to = "nb", "both"
        self.assertEqual(describe_identity(self.world, marta), "No binario · le atraen hombres y mujeres")
        marta.gender, marta.age = "f", 12
        self.assertEqual(describe_identity(self.world, marta), "Niña", "of a child, only what they are")

    def test_the_date_and_a_birthday(self) -> None:
        world, marta = self.world, self.marta
        self.assertEqual(describe_date(world), "1 ene 2226")
        world.clock.day = 62
        self.assertEqual(describe_date(world), "3 mar 2226")
        marta.born = world.clock.day - DAYS_PER_YEAR * 41
        marta.age = 41
        self.assertEqual(describe_age(world, marta), "41 años · cumple el 3 de marzo")
        self.assertTrue(has_birthday(world, marta))
        world.clock.day += 1
        self.assertFalse(has_birthday(world, marta))
        marta.born = world.clock.day
        self.assertFalse(has_birthday(world, marta), "the day somebody is born is no birthday")

    def test_their_kin_are_listed_with_what_they_are_and_where(self) -> None:
        world = self.world
        self.assertEqual(kin_rows(world, self.marta), [("vera", "Vera", "Hermana", "")])
        self.assertEqual(kin_rows(world, world.residents["paco"]), [("bruno", "Bruno", "Hermano", KIN_ELSEWHERE)])
        self.assertEqual(kin_rows(world, world.residents["ines"]), [])
        elder, younger = _family(world)
        rows = {row[0]: row for row in kin_rows(world, self.marta)}
        self.assertEqual(rows["raul"][2:], ("Marido", ""))
        self.assertEqual(rows[elder][3], "")
        self.assertEqual(rows[younger][3], KIN_CARRIED)
        self.assertEqual(list(rows)[0], "raul", "whoever they married comes first")
        bundle = world.bundles.pop(younger)
        world.deaths.append(Death(younger, bundle.name, world.clock.total_minutes, "el abandono"))
        self.assertEqual({row[0]: row for row in kin_rows(world, self.marta)}[younger][3], KIN_DEAD)

    def test_what_is_going_on_in_their_family_is_said(self) -> None:
        world, marta = self.world, self.marta
        self.assertEqual(family_notes(world, marta), [])
        marta.couple_with = "raul"
        world.residents["raul"].couple_with = "marta"
        marta.expecting_with = "raul"
        self.assertEqual(family_notes(world, marta), ["Pareja de Raúl", "Espera una criatura de Raúl"])
        child = world.children.give_birth(world, marta)
        self.assertEqual(family_notes(world, marta), ["Pareja de Raúl", f"Lleva a cuestas a {child.name}"])

    def test_what_they_take_is_said_as_it_has_been_seen(self) -> None:
        world, marta = self.world, self.marta
        now = world.clock.total_minutes
        self.assertEqual(habit_rows(world, marta), [])
        marta.under.append(Intake("liquor", now + 60, now + 120, "drunk"))
        marta.habits["liquor"] = Habit(uses=4, last_taken=now - 9999, dependent=True)
        marta.habits["cigarette"] = Habit(uses=9, recovered=True)
        said = [text for text, _ in habit_rows(world, marta)]
        self.assertEqual(said[0], "Bajo los efectos: aguardiente")
        self.assertIn("No sabe pasar sin: aguardiente · le falta", said)
        self.assertTrue(any(text.startswith("Lo dejó:") for text in said))
        # Once it has worn off, it is what comes after it that is on them.
        marta.under[0].until = now
        self.assertEqual(habit_rows(world, marta)[0][0], "Lo que viene después: aguardiente")

    def test_sleeping_on_the_ground_is_said(self) -> None:
        self.marta.activity = Activity(SLEEP_ROUGH_ACTION, None, [], 100)
        self.assertIn("suelo", describe_action(self.world, self.marta))


class _Shell(unittest.TestCase):
    """The real game shell without a window, on the settlement that comes ready made."""

    illustrated = True

    def setUp(self) -> None:
        for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            self.addCleanup(self._restore_driver, variable, os.environ.get(variable))
            os.environ[variable] = "dummy"
        from game.game import Game

        self.folder = None
        if self.illustrated:
            keep = tempfile.TemporaryDirectory()
            self.addCleanup(keep.cleanup)
            self.folder = Path(keep.name) / "illustrations"
            self.folder.mkdir()
        self.game = Game(illustrations_dir=self.folder, voices_dir=None, start_in_menu=False)
        self.addCleanup(pygame.quit)
        self.view, self.hud, self.world = self.game.global_view, self.game.global_view.hud, self.game.world

    @staticmethod
    def _restore_driver(variable: str, previous: str | None) -> None:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous

    def _show(self, resident_id: str) -> None:
        self.hud.select_resident(resident_id)
        self.view.centre_on_resident(resident_id)
        self.view.render()


class SubstancesOnScreenTests(_Shell):
    """Something seen to be taken, and seen on whoever is under it."""

    def _under(self, resident_id: str, item_id: str, sign: str) -> None:
        now = self.world.clock.total_minutes
        self.world.residents[resident_id].under.append(Intake(item_id, now + 100, now + 200, sign))

    def test_how_it_was_taken_is_seen_over_their_head(self) -> None:
        from scenes.global_view import ROUTE_MARKS, TAKEN_MARK

        routes = self.world.registries.substances.routes
        self.assertEqual(set(ROUTE_MARKS), set(routes), "a mark for each way there is of taking something")
        self.assertEqual(len(set(ROUTE_MARKS.values())), len(routes), "and each its own")
        residents = list(self.world.residents)
        for resident_id, route in zip(residents, routes):
            event = DomainEvent("substance_taken", 10, "", [resident_id], data={"item_id": "liquor", "route": route})
            self.view.on_events([event])
            self.assertEqual(self.view.mark_over(resident_id), ROUTE_MARKS[route])
        other = DomainEvent("substance_taken", 10, "", [residents[-1]], data={"item_id": "liquor", "route": "rubbed_on"})
        self.view.on_events([other])
        self.assertEqual(self.view.mark_over(residents[-1]), TAKEN_MARK, "a way a pack brings is still seen")
        self.view.render()

    def test_whoever_is_under_something_reels_and_nobody_else_does(self) -> None:
        view, marta = self.view, self.world.residents["marta"]
        self.assertIsNone(view.under_sign(marta))
        self.assertEqual(view.sway(marta), 0.0)
        self._under("marta", "liquor", "drunk")
        self.assertEqual(view.under_sign(marta), "drunk")
        reach = set()
        for step in range(40):
            view.time = step * 0.07
            reach.add(round(view.sway(marta), 3))
        self.assertGreater(max(reach), 0.12, "far enough to either side to be seen from the map")
        self.assertLess(min(reach), -0.12)
        self.assertEqual(view._status_icon(marta, resting=False), "dizzy")
        # It wears off, and they are steady again.
        marta.under[0].until = self.world.clock.total_minutes
        self.assertEqual(view.sway(marta), 0.0)

    def test_where_they_stand_goes_with_how_they_reel(self) -> None:
        view = self.view
        self._under("marta", "liquor", "drunk")
        self._show("marta")
        places = set()
        for step in range(12):
            view.time = step * 0.11
            view.render()
            places.add(view.hitboxes["marta"].centerx)
        self.assertGreater(len(places), 1)

    def test_smoke_hangs_round_whoever_smokes_and_they_walk_straight(self) -> None:
        view, paco = self.view, self.world.residents["paco"]
        self._under("paco", "cigarette", "smoke")
        self.assertEqual(view.sway(paco), 0.0)
        self.assertIsNone(view._status_icon(paco, resting=False))
        self._show("paco")
        top = view.hitboxes["paco"].midtop
        clean = view.canvas.copy()
        paco.under.clear()
        view.render()
        over = pygame.Rect(top[0] - 12, top[1] - 22, 24, 22)
        with_smoke = pygame.image.tobytes(clean.subsurface(over), "RGBA")
        without = pygame.image.tobytes(view.canvas.subsurface(over), "RGBA")
        self.assertNotEqual(with_smoke, without, "there is smoke over their head, and none once it has worn off")


class KinPanelTests(_Shell):
    """Who a resident is and whose, in their panel, and the families of everybody on a screen."""

    def test_the_panel_turns_to_who_they_are_and_back(self) -> None:
        from ui.resident_panel import KIN_TAB, LIFE_TAB, TASTES_TAB, kin_hitbox, tab_hitbox

        self._show("marta")
        panel = self.hud.layout.panel
        self.view.click(kin_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, KIN_TAB)
        self.view.render()
        self.view.click(tab_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, LIFE_TAB, "the way back")
        self.view.click(tab_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, TASTES_TAB)
        self.view.click(kin_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, KIN_TAB, "from any face of it")
        self.view.click(kin_hitbox(panel).center)
        self.assertEqual(self.hud.panel_tab, LIFE_TAB)

    def test_one_of_their_kin_who_lives_here_is_picked_from_it_and_no_other(self) -> None:
        from ui.resident_panel import kin_hitboxes

        elder, younger = _family(self.world)
        self._show("marta")
        self.hud.toggle_panel_kin()
        self.view.render()
        boxes = dict((person_id, box) for box, person_id in kin_hitboxes(self.hud.layout.panel, self.world, self.world.residents["marta"]))
        self.assertIn("vera", boxes)
        self.assertIn(elder, boxes)
        self.assertNotIn(younger, boxes, "a child still carried is nobody to select")
        self.view.click(boxes["vera"].center)
        self.assertEqual(self.hud.selected_id, "vera")
        self.view.render()

    def test_the_families_are_asked_for_from_the_roster_and_somebody_is_picked_there(self) -> None:
        from ui.resident_panel import roster_tree_hitbox

        game, view = self.game, self.view
        _family(self.world)
        view.render()
        view.click(roster_tree_hitbox(self.hud.layout.panel).center)
        game.sync_scenes()
        self.assertEqual(game.scene_name, "family")
        screen = game.family_view
        screen.render()
        day, minute = self.world.clock.day, self.world.clock.total_minutes
        game.advance_simulation(5.0)
        self.assertEqual((self.world.clock.day, self.world.clock.total_minutes), (day, minute), "time stands still there")
        self.assertEqual(set(screen.tree.places), set(screen.tree.people))
        # Somebody who does not live here is nobody to pick.
        screen.click(screen.face_rect("bruno").center)
        self.assertFalse(screen.closed)
        screen.click(screen.face_rect("vera").center)
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        self.assertEqual(self.hud.selected_id, "vera")

    def test_it_opens_about_whoever_is_selected_and_escape_leaves_things_as_they_were(self) -> None:
        game = self.game
        self.hud.select_resident("paco")
        self.view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F7, mod=0, unicode=""))
        game.sync_scenes()
        self.assertEqual((game.scene_name, game.family_view.focus), ("family", "paco"))
        game.family_view.pan(40, 0)
        game.family_view.render()
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        game.sync_scenes()
        self.assertEqual((game.scene_name, self.hud.selected_id), ("global", "paco"))


class ChildrenOnScreenTests(_Shell):
    """Children as they are seen: a head and a blanket until they are ten, and a small body from then until grown."""

    def test_the_body_comes_up_to_its_drawn_size_a_little_at_each_birthday(self) -> None:
        from scenes.body_stage import grown_share

        marta = self.world.residents["marta"]
        shares = {}
        for age in (10, 11, 14, 17, 18, 40):
            marta.age = age
            shares[age] = round(grown_share(self.world, marta), 3)
        self.assertEqual(shares, {10: 0.6, 11: 0.65, 14: 0.8, 17: 0.95, 18: 1.0, 40: 1.0})

    def test_a_child_is_shown_with_a_smaller_body_under_the_same_head(self) -> None:
        from graphics.doll import draw_doll
        from skeleton.plan import builtin_plan
        from skeleton.rig import Skeleton

        view = self.view
        doll = view._doll_of("marta")
        plan = doll.plan or builtin_plan()
        skeleton = Skeleton(plan, "doll_right")
        skeleton.set_pose(plan.pose("doll_right"))

        def drawn(grown: float) -> pygame.Rect:
            paper = pygame.Surface((400, 400), pygame.SRCALPHA)
            # About the ground its soles are on, which is a little under the spot between its feet.
            draw_doll(paper, doll, plan, skeleton, (200, 360), 8.0, None, grown, (0.0, doll.standing(plan)[3]))
            return paper.get_bounding_rect()

        whole, small = drawn(1.0), drawn(0.6)
        self.assertLessEqual(abs(small.bottom - whole.bottom), 2, "it stands on the ground it stood on")
        self.assertLess(small.height, whole.height * 0.9)
        self.assertGreater(small.height, whole.height * 0.62, "the head is not brought down with the body")

    def test_whoever_is_not_grown_has_the_one_look_children_have_until_they_are_drawn(self) -> None:
        view = self.view
        elder, _ = _family(self.world)
        child, other = self.world.residents[elder], self.world.residents["lucia"]
        other.age = 13
        self.assertIs(view._doll_for(child), view._doll_for(other), "one look for all of them")
        self.assertIsNot(view._doll_for(child), view._doll_for(self.world.residents["marta"]))
        self._show(elder)
        grown = self.world.residents["raul"]
        self._show("raul")
        self.assertLess(self.view.hitboxes[elder].height, self.view.hitboxes[grown.resident_id].height)

    def test_a_child_still_carried_is_on_the_back_of_whoever_has_it(self) -> None:
        view = self.view
        _, younger = _family(self.world)
        bundle, marta = self.world.bundles[younger], self.world.residents["marta"]
        self.assertEqual((bundle.place, bundle.carried_by), (CARRIED, "marta"))
        self._show("marta")
        x, bottom, depth = view.bundle_spot(bundle)
        box = view.hitboxes["marta"]
        place = view._canvas_point(x, bottom)
        self.assertTrue(box.inflate(16, 4).collidepoint(place), "by their back, and off the ground")
        self.assertLess(place[1], box.bottom - 4)
        from scenes.body_stage import ground_spot

        self.assertLess(depth, ground_spot(marta.x, marta.y)[1], "behind them, who are in front of it")
        picture = view.bundle_shown(bundle, 20)
        self.assertGreater(picture.get_bounding_rect().height, 12)
        self.assertIs(view.bundle_shown(bundle, 20), picture, "made once and kept")

    def test_put_down_it_is_where_it_was_left_with_its_name_over_it(self) -> None:
        view = self.view
        _, younger = _family(self.world)
        bundle, marta = self.world.bundles[younger], self.world.residents["marta"]
        bundle.carried_by, bundle.place, bundle.x, bundle.y = None, GROUND, marta.x + 2, marta.y + 2
        self._show("marta")
        x, bottom, _ = view.bundle_spot(bundle)
        self.assertEqual((int(x // 16), int((bottom - 1) // 16)), (bundle.x, bundle.y))
        self.assertEqual([name.get_width() for name, _ in view._bundle_names], [view.font.width(bundle.name)])
        # From afar there are only faces, and a child still carried has none of its own on the map.
        view.set_zoom(0)
        view.render()
        self.assertEqual(view._bundle_names, [])

    def test_when_somebody_is_born_the_screen_to_draw_them_opens_and_escape_leaves_it_for_later(self) -> None:
        game, world = self.game, self.world
        marta = world.residents["marta"]
        marta.expecting_with = "raul"
        child = world.children.give_birth(world, marta)
        game.global_view.on_events(world.events.drain())
        game.sync_scenes()
        self.assertEqual(game.scene_name, "editor")
        self.assertEqual(game.doll_editor.resident_id, child.child_id)
        game.doll_editor.render()
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        self.assertIn(child.child_id, world.bundles)
        game.global_view.render()


class NoDrawingsTests(_Shell):
    """The same without anywhere to keep drawings: nothing asks to be drawn, and everything is still shown."""

    illustrated = False

    def test_a_birth_asks_for_no_drawing_and_children_are_still_seen(self) -> None:
        game, world = self.game, self.world
        elder, younger = _family(world)
        game.global_view.on_events(world.events.drain())
        game.sync_scenes()
        self.assertEqual(game.scene_name, "global")
        self._show("raul")
        grown = self.view.hitboxes["raul"].height
        self._show(elder)
        self.assertLess(self.view.hitboxes[elder].height, grown, "the game's own small body is brought down too")
        bundle = world.bundles[younger]
        bundle.carried_by, bundle.place = None, GROUND
        self.view.render()

    def test_whoever_sleeps_on_the_ground_and_whoever_reels_are_drawn(self) -> None:
        world, view = self.world, self.view
        paco = world.residents["paco"]
        paco.activity = Activity(SLEEP_ROUGH_ACTION, None, [], 100)
        paco.activity.using = True
        now = world.clock.total_minutes
        world.residents["marta"].under.append(Intake("cigarette", now + 50, now + 90, "smoke"))
        self._show("paco")
        self.assertIn("paco", view.hitboxes)
        self.assertEqual(view._status_icon(paco, resting=True), "sleep")


class RestOfKinOnScreenTests(_Shell):
    """The date, a birthday, a wedding, whoever sleeps on the ground and whoever knocks at the gate."""

    def test_the_date_is_by_the_clock_with_room_for_any_date(self) -> None:
        hud, font = self.hud, self.view.font
        self.world.clock.day = 271
        self.assertEqual(describe_date(self.world), "28 sep 2226")
        self.assertLessEqual(font.width(describe_date(self.world)), hud.plaque.width - 4)
        self.assertGreater(hud.clock_left, hud.plaque.right)
        self.view.render()
        self.assertLess(hud.zoom_buttons[0].rect.left - hud.counts_left, hud.layout.top.width)

    def test_two_who_marry_wear_it_and_a_birthday_is_worn_all_day(self) -> None:
        view, world = self.view, self.world
        event = DomainEvent("couple_married", 65, "", ["marta", "raul"])
        view.on_events([event])
        self.assertEqual((view.mark_over("marta"), view.mark_over("raul")), ("rings", "rings"))
        view.time += 6.0
        self.assertEqual(view.mark_over("marta"), "rings", "for longer than what is taken or learned")
        lucia = world.residents["lucia"]
        lucia.born = world.clock.day - DAYS_PER_YEAR * lucia.age
        self.assertTrue(has_birthday(world, lucia))
        self._show("lucia")

    def test_whoever_sleeps_on_the_ground_is_seen_lying_there(self) -> None:
        view, paco = self.view, self.world.residents["paco"]
        self._show("paco")
        standing = view.hitboxes["paco"]
        paco.activity = Activity(SLEEP_ROUGH_ACTION, None, [], 100)
        paco.activity.using = True
        self.assertTrue(view.sleeps_rough(paco))
        view.render()
        lying = view.hitboxes["paco"]
        self.assertGreater(lying.width, lying.height, "lying, and not standing")
        self.assertLess(lying.height, standing.height)
        # On a window it is the whole of them that is seen, going down to lie curled up on the
        # ground (P49): there is no blanket over them any more.
        self.assertIsNotNone(view._doll_for(paco))
        self.assertEqual(view._rough, [])
        rough = view.poses.rough
        self.assertIn(view.bodies.characters["paco"].clip, (rough.down.clip, rough.asleep.clip))

    def _knock(self, together: bool = True) -> list:
        world = self.world
        pair = world.registries.family.arrive_together[0]
        newcomer = next(each for each in world.registries.world_events.newcomers if each.newcomer_id == pair[0])
        self.assertTrue(world.happenings._come_to_gate(world, world.residents["marta"], newcomer, alone=not together))
        gate = next(iter(world.entry_tiles()))
        self.view.centre_on((gate[0] + 0.5, gate[1] - 2))
        self.view.render()
        return self.view.strangers()

    def test_two_at_the_gate_are_seen_together_and_a_click_on_one_opens_the_answer(self) -> None:
        game, view, world = self.game, self.view, self.world
        self.assertEqual(view.strangers(), [])
        strangers = self._knock()
        self.assertEqual([each.resident_id for each in strangers], world.gate_party)
        self.assertEqual(len(strangers), 2)
        first, second = strangers
        self.assertEqual((second.x - first.x, second.y - first.y), (1, 0), "side by side")
        for each in strangers:
            self.assertIn(each.resident_id, view.hitboxes)
            self.assertNotIn(each.resident_id, world.residents)
        view.click(view.hitboxes[first.resident_id].center)
        game.sync_scenes()
        self.assertEqual(game.scene_name, "interaction")
        self.assertEqual(game.interaction_view.decision.kind, "strangers")
        game.interaction_view.render()
        self.assertTrue(game.interaction_view.dock.contains(game.interaction_view.second_face_rect()))
        self.assertEqual(len(game.interaction_view.buttons), 5, "both, either of them, as they think best, or neither")
        # Once it is answered there is nobody at the gate to see.
        game.interaction_view.choose("close")
        game.interaction_view.render()
        self.assertEqual(view.strangers(), [])

    def test_one_alone_is_seen_too(self) -> None:
        strangers = self._knock(together=False)
        self.assertEqual(len(strangers), 1)
        self.view.set_zoom(0)
        self.view.render()
        self.assertIn(strangers[0].resident_id, self.view.hitboxes, "from afar they are a face like anybody")


class CreatorIdentityTests(_Shell):
    """Who the first resident is, said where they are made."""

    illustrated = False

    def test_who_they_are_is_said_and_they_are_made_so(self) -> None:
        from scenes.resident_creator import DRAWN, GENDER, SEX

        game = self.game
        game.new_game(seed=5)
        creator = game.creator
        self.assertIn("libido", creator.sliders)
        creator.set_name("Olga")
        creator.set_identity(SEX, "m")
        self.assertEqual(creator.identity[GENDER], "m", "until it is said otherwise, they are what their body is")
        creator.set_identity(GENDER, "nb")
        creator.set_identity(SEX, "f")
        self.assertEqual(creator.identity[GENDER], "nb", "once said, it stays said")
        creator.set_identity(DRAWN, "f")
        creator.set_identity(DRAWN, "everybody")
        creator.personality["libido"] = 80.0
        creator.render()
        button = next(button for button in creator.buttons if button.intent == ("identity", GENDER, "bi"))
        creator.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(button.rect.centerx * 2, button.rect.centery * 2)))
        created = creator.create()
        resident = game.world.residents[created]
        self.assertEqual((resident.sex, resident.gender, resident.drawn_to), ("f", "bi", "f"))
        self.assertEqual(resident.personality.libido, 80.0)

    def test_nothing_of_it_is_on_top_of_anything_else(self) -> None:
        game = self.game
        game.new_game(seed=5)
        creator = game.creator
        boxes = [button.rect for button in creator.buttons] + [slider.rect for slider in creator.sliders.values()]
        for index, box in enumerate(boxes):
            self.assertTrue(creator.canvas.get_rect().contains(box))
            self.assertEqual([other for other in boxes[index + 1 :] if box.colliderect(other)], [])


if __name__ == "__main__":
    unittest.main()
