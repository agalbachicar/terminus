"""
Copyright (C) 2017 Open Source Robotics Foundation

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from shapely.geometry import LineString
from geometry.point import Point

from waypoint import Waypoint


class PathGeometry(object):

    def __init__(self, elements):
        self._elements = elements
        self._waypoints = None

    @classmethod
    def from_path(cls, path):
        points = path.control_points()
        return cls.from_control_points(points)

    @classmethod
    def from_control_points(cls, control_points):
        if len(control_points) < 2:
            raise ValueError("Can't create a geometry from an empty path")
        instance = cls([])
        instance._build_geometry_from(control_points)
        return instance

    def elements_count(self):
        return len(self._elements)

    def elements(self):
        return self._elements

    def element_at(self, index):
        return self._elements[index]

    def first_element(self):
        return self.element_at(0)

    def last_element(self):
        return self.element_at(-1)

    def start_point(self):
        return self.element_at(0).start_point()

    def end_point(self):
        return self.element_at(-1).end_point()

    def length(self):
        return sum(map(lambda element: element.length(), self.elements()))

    def replace_element_at(self, index, new_element):
        self._elements[index] = new_element
        self._waypoints = None

    def simplify(self):
        """
        Reduce the number of geometric primitives in the path by removing
        redundant ones (e.g. merges two contiguous collinear line segments into
        a single one)
        """
        new_primitives = []
        previous_primitive = self._elements[0]
        index = 1
        while (index < len(self._elements)):
            current_primitive = self._elements[index]
            if previous_primitive.can_be_merged_with(current_primitive):
                previous_primitive = previous_primitive.merge(current_primitive)
            else:
                new_primitives.append(previous_primitive)
                previous_primitive = current_primitive
            index += 1
        new_primitives.append(previous_primitive)
        self._elements = new_primitives

    def split_in(self, waypoints):
        primitives = []
        waypoint_index = 0
        for element in self.elements():
            current_center = waypoints[waypoint_index].center()
            pairs = []
            while current_center != element.end_point():
                waypoint_index += 1
                next_center = waypoints[waypoint_index].center()
                pairs.append((current_center, next_center))
                current_center = next_center
            primitives.extend(element.split_into(pairs))
        return self.__class__(primitives)

    def waypoints(self, lane, builder):
        if not self._waypoints:
            elements = list(self.elements())
            road_nodes = lane.road().nodes()
            nodes_by_point = builder.index_nodes(road_nodes)
            nodes_by_point[self.start_point().rounded()] = road_nodes[0]
            nodes_by_point[self.end_point().rounded()] = road_nodes[-1]
            self._waypoints = []
            for element in elements:
                point = element.start_point()
                node = nodes_by_point[point.rounded()]
                waypoint = Waypoint(lane, self, point, element.start_heading(), node)
                self._waypoints.append(waypoint)
            # We need to add the last way point
            last_element = elements[-1]
            point = element.end_point()
            node = nodes_by_point[point.rounded()]
            waypoint = Waypoint(lane, self, point, last_element.end_heading(), node)
            self._waypoints.append(waypoint)
        return self._waypoints

    def point_at_linear_offset(self, reference_point, offset):
        matches = []
        for element in self.elements():
            point = element.point_at_linear_offset(reference_point, offset)
            if point:
                rounded_point = point.rounded_to(10)
                if rounded_point not in matches:
                    matches.append(rounded_point)
        if len(matches) == 1:
            return matches[0]
        # TODO: Replace this with an assertion
        if len(matches) > 2:
            raise ValueError("Too many matches")
        else:
            if offset < 0:
                return matches[0]
            else:
                return matches[1]

    def heading_at_point(self, point):
        # TODO: Improve performance
        offset = self.offset_for_point(point)
        return self.heading_at_offset(offset)

    def heading_at_offset(self, offset):
        # TODO: Refactor with point_at_offset
        remaining_distance = offset
        for element in self.elements():
            if element.length() < remaining_distance:
                remaining_distance -= element.length()
            else:
                return element.heading_at_offset(remaining_distance)
        message = "Provided offset ({0}) is greater that path length ({1})".format(offset, self.length())
        raise ValueError(message)

    def point_at_offset(self, offset):
        remaining_distance = offset
        for element in self.elements():
            if element.length() < remaining_distance:
                remaining_distance -= element.length()
            else:
                return element.point_at_offset(remaining_distance)
        message = "Provided offset ({0}) is greater that path length ({1})".format(offset, self.length())
        raise ValueError(message)

    def offset_for_point(self, point):
        accumulated_distance = 0
        for element in self.elements():
            if element.includes_point(point):
                return accumulated_distance + element.offset_for_point(point)
            else:
                accumulated_distance += element.length()
        message = "Point {0} does not exist in path {1}".format(point, self)
        raise ValueError(message)

    def line_interpolation_points(self):
        points = []
        for element in self.elements():
            new_points = element.line_interpolation_points()
            # Last point of previous element and first point of current
            # one are the same. Avoid having it twice
            if points:
                points.pop()
            points.extend(new_points)
        return points

    def connect_waypoints(self, exit_waypoint, entry_waypoint):
        raise NotImplementedError()

    def _build_geometry_from(self, path):
        raise NotImplementedError()

    def __repr__(self):
        parts = ""
        for element in self.elements():
            parts += "\n" + str(element)
        return "Path geometry" + parts
